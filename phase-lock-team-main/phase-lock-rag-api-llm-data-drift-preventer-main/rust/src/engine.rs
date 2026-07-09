use std::collections::{HashMap, HashSet, VecDeque};
use std::f64::consts::PI;

#[derive(Debug, Clone)]
pub struct EngineOutput {
    pub stabilized_vector: Vec<f64>, // always len 24
    pub drift_score: f64,            // [0, 1]
    pub euler_chi: f64,
    pub genus: f64,
    pub beta0: f64,
    pub beta1: f64,
    pub energy_level: f64,
    pub stress_level: f64,
    pub drift_ema: f64,
    pub drift_trend: f64,
    pub topology_volatility: f64,
    pub surgery_rate: f64,
    pub surgery_total: f64,
}

#[derive(Debug, Clone)]
pub struct EngineState {
    nx: usize,
    ny: usize,
    n_fields: usize,
    seed: u64,
    tick: u64,
    rng_state: u64,
    state_vec: [f64; 24],
    vertices: Vec<[f64; 2]>,
    faces: HashSet<[usize; 3]>,
    edges: HashSet<(usize, usize)>,
    phi: Vec<Vec<f64>>, // n_fields x n_vertices
    drift_ema: f64,
    drift_trend: f64,
    energy_ema: f64,
    stress_ema: f64,
    topology_volatility_ema: f64,
    surgery_events: u64,
    surgery_trials: u64,
}

impl EngineState {
    pub fn new(nx: usize, ny: usize, n_fields: usize, seed: u64) -> Self {
        let mut state = Self {
            nx: nx.max(2),
            ny: ny.max(2),
            n_fields: n_fields.max(1),
            seed,
            tick: 0,
            rng_state: seed ^ 0x9E37_79B9_7F4A_7C15,
            state_vec: [0.0_f64; 24],
            vertices: Vec::new(),
            faces: HashSet::new(),
            edges: HashSet::new(),
            phi: Vec::new(),
            drift_ema: 0.0,
            drift_trend: 0.0,
            energy_ema: 0.0,
            stress_ema: 0.0,
            topology_volatility_ema: 0.0,
            surgery_events: 0,
            surgery_trials: 0,
        };

        for (i, v) in state.state_vec.iter_mut().enumerate() {
            let t = (seed as f64 * 0.013) + (i as f64 * 0.37);
            *v = (t.sin() * 0.5 + t.cos() * 0.25).clamp(-1.0, 1.0);
        }

        state.make_initial_complex();
        state.initialize_fields();
        state
    }

    pub fn stabilize(&mut self, metric_window: Vec<f64>, embedding: Option<Vec<f64>>) -> EngineOutput {
        let clean_metrics: Vec<f64> = metric_window
            .into_iter()
            .map(|x| if x.is_finite() { x } else { 0.0 })
            .collect();

        let n = clean_metrics.len().max(1) as f64;
        let metric_mean = clean_metrics.iter().sum::<f64>() / n;
        let metric_var = clean_metrics
            .iter()
            .map(|x| {
                let d = *x - metric_mean;
                d * d
            })
            .sum::<f64>()
            / n;
        let metric_std = metric_var.sqrt();

        let metric_abs_mean = clean_metrics.iter().map(|x| x.abs()).sum::<f64>() / n;
        let scale = (metric_std + 0.5 * metric_abs_mean + 1e-6).max(1e-6);
        let anchors = self.sample_24(&clean_metrics);

        let (emb_mean, emb_energy) = match embedding {
            Some(v) if !v.is_empty() => {
                let finite_vals: Vec<f64> = v.into_iter().filter(|x| x.is_finite()).collect();
                if finite_vals.is_empty() {
                    (0.0, 0.0)
                } else {
                    let denom = finite_vals.len() as f64;
                    let m = finite_vals.iter().sum::<f64>() / denom;
                    let e = finite_vals.iter().map(|x| x * x).sum::<f64>() / denom;
                    (m, e.sqrt())
                }
            }
            _ => (0.0, 0.0),
        };

        let mut target24 = [0.0_f64; 24];
        for i in 0..24 {
            target24[i] = ((anchors[i] - metric_mean) / scale).tanh();
        }

        let steps = clean_metrics.len().clamp(24, 220);
        let dt = 0.0015 + 0.0005 * (metric_std.tanh().abs());

        for local_step in 0..steps {
            self.step(dt, local_step as u64, &target24, emb_mean, emb_energy);
        }

        let innovation = self
            .state_vec
            .iter()
            .zip(target24.iter())
            .map(|(s, t)| (s - t).abs())
            .sum::<f64>()
            / 24.0;

        let spread = self.state_vec.iter().map(|v| v.abs()).sum::<f64>() / 24.0;
        let volatility = (metric_std / (metric_abs_mean + 1e-6)).tanh().abs();

        let euler_chi = self.euler_characteristic();
        let genus = self.genus();
        let (beta0, beta1) = self.betti_numbers();

        let stress_now_vec = self.stress();
        let stress_level = if stress_now_vec.is_empty() {
            0.0
        } else {
            stress_now_vec.iter().sum::<f64>() / (stress_now_vec.len() as f64)
        };

        let energy_level = self.energy();

        let topology_pressure = ((genus / 12.0) + (beta1 / 8.0) + (stress_level / 3.0).tanh()).clamp(0.0, 1.0);
        let drift_score = (0.40 * innovation + 0.24 * volatility + 0.16 * spread + 0.20 * topology_pressure)
            .clamp(0.0, 1.0);

        let prev_drift_ema = self.drift_ema;
        self.drift_ema = 0.90 * self.drift_ema + 0.10 * drift_score;
        self.drift_trend = self.drift_ema - prev_drift_ema;
        self.energy_ema = 0.92 * self.energy_ema + 0.08 * energy_level;
        self.stress_ema = 0.92 * self.stress_ema + 0.08 * stress_level;

        let raw_topo_volatility = (self.genus().abs() + beta1.abs() + (self.euler_characteristic() / 10.0).abs())
            .clamp(0.0, 20.0)
            / 20.0;
        self.topology_volatility_ema = 0.90 * self.topology_volatility_ema + 0.10 * raw_topo_volatility;

        let surgery_rate = if self.surgery_trials == 0 {
            0.0
        } else {
            (self.surgery_events as f64) / (self.surgery_trials as f64)
        };

        EngineOutput {
            stabilized_vector: self.state_vec.to_vec(),
            drift_score,
            euler_chi,
            genus,
            beta0,
            beta1,
            energy_level: self.energy_ema,
            stress_level: self.stress_ema,
            drift_ema: self.drift_ema,
            drift_trend: self.drift_trend,
            topology_volatility: self.topology_volatility_ema,
            surgery_rate,
            surgery_total: self.surgery_events as f64,
        }
    }

    fn make_initial_complex(&mut self) {
        let nx = self.nx;
        let ny = self.ny;

        self.vertices.clear();
        self.faces.clear();
        self.edges.clear();

        for j in 0..ny {
            let y = -3.0 + (6.0 * j as f64) / ((ny - 1) as f64);
            for i in 0..nx {
                let x = -3.0 + (6.0 * i as f64) / ((nx - 1) as f64);
                self.vertices.push([x, y]);
            }
        }

        let idx = |i: usize, j: usize| -> usize { j * nx + i };
        for j in 0..(ny - 1) {
            for i in 0..(nx - 1) {
                let a = idx(i, j);
                let b = idx(i + 1, j);
                let c = idx(i, j + 1);
                let d = idx(i + 1, j + 1);

                self.create_face(a, b, d);
                self.create_face(a, d, c);
            }
        }

        self.rebuild_edges();
    }

    fn initialize_fields(&mut self) {
        let n_vertices = self.vertices.len();
        self.phi = vec![vec![0.0; n_vertices]; self.n_fields];

        for n in 0..self.n_fields {
            let k = (n + 1) as f64;
            for i in 0..n_vertices {
                let x = self.vertices[i][0];
                let y = self.vertices[i][1];
                let noise = 0.05 * self.rand_sym();
                self.phi[n][i] =
                    0.25 * (k * x / 3.0).sin() * (((k + 1.0) * y) / 4.0).cos() + noise;
            }
        }
    }

    fn step(&mut self, dt: f64, local_step: u64, target24: &[f64; 24], emb_mean: f64, emb_energy: f64) {
        let n_vertices = self.vertices.len();
        if n_vertices == 0 {
            return;
        }

        let mean_field = self.mean_field();
        let resonance = self.resonant_forcing();
        let symbolic = self.symbolic_forcing();

        let mut new_phi = self.phi.clone();

        for n in 0..self.n_fields {
            let field = &self.phi[n];
            let l_field = self.laplacian_apply(field);
            let l2_field = self.laplacian_apply(&l_field);

            for i in 0..n_vertices {
                let lap = -l_field[i];
                let reaction = match n {
                    0 => field[i] - field[i].powi(3),
                    1 => field[i].sin() + 0.1 * field[i].powi(3),
                    2 => field[i] * (1.0 - field[i] * field[i]),
                    3 => -0.2 * field[i].powi(5),
                    4 => field[i] * (field[i].abs() + 1e-3).ln(),
                    5 => field[i].powi(3) * lap,
                    6 => -0.01 * l2_field[i],
                    7 => 0.1 * field[i].clamp(-1.5, 1.5).sinh(),
                    8 => field[i].powi(2) * lap,
                    _ => -0.005 * l2_field[i],
                };

                let coupling = 0.05 * resonance[i] * (mean_field[i] - field[i]);
                let forcing = 0.05 * symbolic[i] + 0.02 * emb_mean.tanh() + 0.01 * emb_energy.tanh();

                new_phi[n][i] = (new_phi[n][i] + dt * (0.08 * lap + 0.35 * reaction + coupling + forcing))
                    .clamp(-3.0, 3.0);
            }
        }

        self.phi = new_phi;

        let field_avg = self
            .phi
            .iter()
            .flat_map(|f| f.iter())
            .copied()
            .sum::<f64>()
            / ((self.n_fields * n_vertices).max(1) as f64);

        let field_var = self
            .phi
            .iter()
            .flat_map(|f| f.iter())
            .map(|v| {
                let d = *v - field_avg;
                d * d
            })
            .sum::<f64>()
            / ((self.n_fields * n_vertices).max(1) as f64);
        let field_std = field_var.sqrt();

        let old = self.state_vec;
        for i in 0..24 {
            let prev = old[(i + 23) % 24];
            let curr = old[i];
            let next = old[(i + 1) % 24];
            let ring_coupling = 0.5 * (prev + next) - curr;

            let phase = (self.tick as f64) * 0.02 + (i as f64) * 0.31 + (self.seed as f64 * 0.001);
            let resonance_drive = (0.6 * phase.sin() + 0.4 * phase.cos()).clamp(-1.0, 1.0);
            let target_drive = target24[i];

            self.state_vec[i] = (curr
                + 0.013 * field_avg
                + 0.006 * field_std * (i as f64).sin()
                + 0.11 * (target_drive - curr)
                + 0.07 * ring_coupling
                + 0.03 * resonance_drive)
                .clamp(-1.0, 1.0);
        }

        let stress = self.stress();
        self.topology_surgery(local_step, &stress);

        self.tick = self.tick.wrapping_add(1);
    }

    fn topology_surgery(&mut self, local_step: u64, stress: &[f64]) {
        if stress.is_empty() {
            return;
        }

        let avg_stress = stress.iter().sum::<f64>() / stress.len() as f64;
        let max_stress = stress.iter().copied().fold(0.0_f64, f64::max);

        if local_step % 20 == 0 {
            self.surgery_trials += 1;
            if self.edge_flip() {
                self.surgery_events += 1;
            }
        }

        if local_step % 60 == 0 && max_stress > 2.5 * avg_stress {
            self.surgery_trials += 1;
            if self.hole_create() {
                self.surgery_events += 1;
            }
        }

        if local_step % 90 == 0 {
            self.surgery_trials += 1;
            if self.hole_close() {
                self.surgery_events += 1;
            }
        }

        if local_step % 120 == 0 {
            if self.genus() < 12.0 {
                self.surgery_trials += 1;
                if self.handle_insert() {
                    self.surgery_events += 1;
                }
            } else {
                self.surgery_trials += 1;
                if self.handle_collapse() {
                    self.surgery_events += 1;
                }
            }
        }

        if local_step % 200 == 0 {
            self.surgery_trials += 1;
            if self.bridge_insert() {
                self.surgery_events += 1;
            }
        }

        if local_step % 300 == 0 {
            self.surgery_trials += 1;
            if self.bridge_delete() {
                self.surgery_events += 1;
            }
        }

        if local_step % 420 == 0 {
            self.surgery_trials += 1;
            if self.face_merge() {
                self.surgery_events += 1;
            }
        }
    }

    fn energy(&self) -> f64 {
        if self.vertices.is_empty() || self.phi.is_empty() {
            return 0.0;
        }

        let mut total = 0.0;
        for field in &self.phi {
            let l_field = self.laplacian_apply(field);
            let grad = field
                .iter()
                .zip(l_field.iter())
                .map(|(f, lf)| f * lf)
                .sum::<f64>();

            let potential = field
                .iter()
                .map(|f| -0.5 * f * f + 0.25 * f.powi(4))
                .sum::<f64>()
                / (field.len().max(1) as f64);

            total += 0.001 * grad + potential;
        }
        total / (self.n_fields.max(1) as f64)
    }

    fn laplacian_apply(&self, values: &[f64]) -> Vec<f64> {
        let n = self.vertices.len();
        let mut out = vec![0.0_f64; n];
        if n == 0 || self.edges.is_empty() {
            return out;
        }

        let mut lengths = Vec::with_capacity(self.edges.len());
        for &(i, j) in &self.edges {
            lengths.push(self.distance(i, j));
        }
        lengths.sort_by(|a, b| a.total_cmp(b));
        let median = lengths[lengths.len() / 2] + 1e-8;

        for &(i, j) in &self.edges {
            let d = self.distance(i, j);
            if d < 0.2 * median {
                continue;
            }

            let w = (-d / median).exp();
            let dv = values[i] - values[j];
            out[i] += w * dv;
            out[j] -= w * dv;
        }
        out
    }

    fn stress(&self) -> Vec<f64> {
        let mean = self.mean_field();
        self.laplacian_apply(&mean).into_iter().map(|v| v.abs()).collect()
    }

    fn mean_field(&self) -> Vec<f64> {
        let n = self.vertices.len();
        let mut out = vec![0.0_f64; n];
        if self.n_fields == 0 {
            return out;
        }

        for field in &self.phi {
            for i in 0..n {
                out[i] += field[i];
            }
        }
        for v in &mut out {
            *v /= self.n_fields as f64;
        }
        out
    }

    fn symbolic_forcing(&self) -> Vec<f64> {
        let mut out = vec![0.0_f64; self.vertices.len()];
        for (i, v) in self.vertices.iter().enumerate() {
            let x = v[0];
            let y = v[1];

            let ix = (((x + 3.0) / 6.0) * 4.0).floor().clamp(0.0, 3.0) as usize;
            let iy = (((y + 3.0) / 6.0) * 6.0).floor().clamp(0.0, 5.0) as usize;
            let idx = ix * 6 + iy;

            out[i] = (0.1 * self.state_vec[idx]).sin();
        }
        out
    }

    fn resonant_forcing(&self) -> Vec<f64> {
        let mut out = vec![0.0_f64; self.vertices.len()];
        for (i, v) in self.vertices.iter().enumerate() {
            let x = v[0];
            let y = v[1];
            let theta = y.atan2(x);
            let r = (x * x + y * y).sqrt();
            out[i] = (12.0 * theta).cos() * (4.0 * r).sin();
        }
        out
    }

    fn euler_characteristic(&self) -> f64 {
        (self.vertices.len() as f64) - (self.edges.len() as f64) + (self.faces.len() as f64)
    }

    fn graph_components(&self) -> usize {
        let n = self.vertices.len();
        if n == 0 {
            return 0;
        }

        let mut adj: Vec<Vec<usize>> = vec![Vec::new(); n];
        for &(i, j) in &self.edges {
            adj[i].push(j);
            adj[j].push(i);
        }

        let mut visited = vec![false; n];
        let mut components = 0usize;

        for start in 0..n {
            if visited[start] {
                continue;
            }
            components += 1;
            let mut q = VecDeque::new();
            q.push_back(start);
            visited[start] = true;

            while let Some(u) = q.pop_front() {
                for &v in &adj[u] {
                    if !visited[v] {
                        visited[v] = true;
                        q.push_back(v);
                    }
                }
            }
        }

        components
    }

    fn betti_numbers(&self) -> (f64, f64) {
        let v = self.vertices.len() as f64;
        let e = self.edges.len() as f64;
        let f = self.faces.len() as f64;
        let beta0 = self.graph_components() as f64;

        let cycle_rank = (e - v + beta0).max(0.0);
        let rank_b2 = f.min(cycle_rank);
        let beta1 = (cycle_rank - rank_b2).max(0.0);
        (beta0, beta1)
    }

    fn genus(&self) -> f64 {
        ((2.0 - self.euler_characteristic()) / 2.0).max(0.0)
    }

    fn edge_face_map(&self) -> HashMap<(usize, usize), Vec<[usize; 3]>> {
        let mut mp: HashMap<(usize, usize), Vec<[usize; 3]>> = HashMap::new();
        for &f in &self.faces {
            let a = f[0];
            let b = f[1];
            let c = f[2];
            for e in [self.edge(a, b), self.edge(b, c), self.edge(a, c)] {
                mp.entry(e).or_default().push(f);
            }
        }
        mp
    }

    fn boundary_edges(&self) -> Vec<(usize, usize)> {
        self.edge_face_map()
            .into_iter()
            .filter_map(|(e, fs)| if fs.len() == 1 { Some(e) } else { None })
            .collect()
    }

    fn edge_flip(&mut self) -> bool {
        let mp = self.edge_face_map();
        let candidates: Vec<((usize, usize), Vec<[usize; 3]>)> = mp
            .into_iter()
            .filter(|(_, fs)| fs.len() == 2)
            .collect();

        if candidates.is_empty() {
            return false;
        }

        let idx = self.rand_index(candidates.len());
        let (shared_edge, fs) = &candidates[idx];
        let f1 = fs[0];
        let f2 = fs[1];
        let shared = [shared_edge.0, shared_edge.1];

        let opp1: Vec<usize> = f1.iter().copied().filter(|v| *v != shared[0] && *v != shared[1]).collect();
        let opp2: Vec<usize> = f2.iter().copied().filter(|v| *v != shared[0] && *v != shared[1]).collect();

        if opp1.len() != 1 || opp2.len() != 1 {
            return false;
        }

        let u = opp1[0];
        let v = opp2[0];
        if u == v || self.edges.contains(&self.edge(u, v)) {
            return false;
        }

        self.faces.remove(&f1);
        self.faces.remove(&f2);

        self.create_face(u, v, shared[0]);
        self.create_face(u, v, shared[1]);
        self.rebuild_edges();
        true
    }

    fn face_merge(&mut self) -> bool {
        if self.faces.is_empty() {
            return false;
        }

        let idx = self.rand_index(self.faces.len());
        let victim = *self.faces.iter().nth(idx).unwrap_or(&[0, 0, 0]);
        if victim[0] == victim[1] {
            return false;
        }
        self.faces.remove(&victim);
        self.rebuild_edges();
        true
    }

    fn bridge_insert(&mut self) -> bool {
        let n = self.vertices.len();
        if n < 2 {
            return false;
        }

        for _ in 0..50 {
            let (i, j) = self.rand_pair(n);
            if self.distance(i, j) > 3.0 {
                let e = self.edge(i, j);
                if !self.edges.contains(&e) {
                    self.edges.insert(e);
                    return true;
                }
            }
        }
        false
    }

    fn bridge_delete(&mut self) -> bool {
        if self.edges.is_empty() {
            return false;
        }

        let mut scored: Vec<(f64, (usize, usize))> = self
            .edges
            .iter()
            .map(|&(i, j)| (self.distance(i, j), (i, j)))
            .collect();
        scored.sort_by(|a, b| b.0.total_cmp(&a.0));

        if let Some((_, e)) = scored.first() {
            self.delete_edge(e.0, e.1);
            return true;
        }
        false
    }

    fn hole_create(&mut self) -> bool {
        if self.faces.is_empty() || self.vertices.is_empty() {
            return false;
        }

        let center = self.vertices[self.rand_index(self.vertices.len())];
        let mut scored: Vec<(f64, [usize; 3])> = self
            .faces
            .iter()
            .map(|&f| {
                let a = self.vertices[f[0]];
                let b = self.vertices[f[1]];
                let c = self.vertices[f[2]];
                let cx = (a[0] + b[0] + c[0]) / 3.0;
                let cy = (a[1] + b[1] + c[1]) / 3.0;
                let d = ((cx - center[0]).powi(2) + (cy - center[1]).powi(2)).sqrt();
                (d, f)
            })
            .collect();
        scored.sort_by(|a, b| a.0.total_cmp(&b.0));

        let remove_count = scored.len().min(8);
        for (_, f) in scored.into_iter().take(remove_count) {
            self.faces.remove(&f);
        }
        self.rebuild_edges();
        true
    }

    fn hole_close(&mut self) -> bool {
        let boundary = self.boundary_edges();
        if boundary.len() < 3 {
            return false;
        }

        let mut used = 0usize;
        for &(i, j) in boundary.iter().take(20) {
            let midpoint = [
                0.5 * (self.vertices[i][0] + self.vertices[j][0]),
                0.5 * (self.vertices[i][1] + self.vertices[j][1]),
            ];

            let mut candidates: Vec<(f64, usize)> = (0..self.vertices.len())
                .filter(|k| *k != i && *k != j)
                .map(|k| {
                    let d = ((self.vertices[k][0] - midpoint[0]).powi(2)
                        + (self.vertices[k][1] - midpoint[1]).powi(2))
                    .sqrt();
                    (d, k)
                })
                .collect();
            candidates.sort_by(|a, b| a.0.total_cmp(&b.0));

            for (_, k) in candidates {
                let f = self.face(i, j, k);
                if !self.faces.contains(&f) {
                    self.create_face(i, j, k);
                    used += 1;
                    break;
                }
            }

            if used >= 6 {
                break;
            }
        }

        self.rebuild_edges();
        used > 0
    }

    fn handle_insert(&mut self) -> bool {
        let n = self.vertices.len();
        if n < 4 {
            return false;
        }

        for _ in 0..100 {
            let (i, j) = self.rand_pair(n);
            let (k, l) = self.rand_pair(n);
            if i == k || i == l || j == k || j == l {
                continue;
            }

            if self.distance(i, j) > 3.0 && self.distance(k, l) > 3.0 {
                self.edges.insert(self.edge(i, j));
                self.edges.insert(self.edge(k, l));
                self.create_face(i, j, k);
                self.create_face(j, k, l);
                self.rebuild_edges();
                return true;
            }
        }
        false
    }

    fn handle_collapse(&mut self) -> bool {
        if self.edges.is_empty() {
            return false;
        }

        let mut long_edges: Vec<(f64, (usize, usize))> = self
            .edges
            .iter()
            .filter_map(|&(i, j)| {
                let d = self.distance(i, j);
                if d > 3.0 {
                    Some((d, (i, j)))
                } else {
                    None
                }
            })
            .collect();

        if long_edges.is_empty() {
            return false;
        }

        long_edges.sort_by(|a, b| b.0.total_cmp(&a.0));
        for (_, e) in long_edges.into_iter().take(2) {
            self.delete_edge(e.0, e.1);
        }
        self.rebuild_edges();
        true
    }

    fn create_face(&mut self, i: usize, j: usize, k: usize) {
        if i == j || j == k || i == k {
            return;
        }
        let f = self.face(i, j, k);
        self.faces.insert(f);
        self.edges.insert(self.edge(i, j));
        self.edges.insert(self.edge(j, k));
        self.edges.insert(self.edge(i, k));
    }

    fn delete_edge(&mut self, i: usize, j: usize) {
        let e = self.edge(i, j);
        self.edges.remove(&e);
        let mut to_remove = Vec::new();
        for &f in &self.faces {
            let a = f[0];
            let b = f[1];
            let c = f[2];
            let has_edge = [self.edge(a, b), self.edge(b, c), self.edge(a, c)]
                .into_iter()
                .any(|x| x == e);
            if has_edge {
                to_remove.push(f);
            }
        }
        for f in to_remove {
            self.faces.remove(&f);
        }
    }

    fn rebuild_edges(&mut self) {
        self.edges.clear();
        for &f in &self.faces {
            self.edges.insert(self.edge(f[0], f[1]));
            self.edges.insert(self.edge(f[1], f[2]));
            self.edges.insert(self.edge(f[0], f[2]));
        }
    }

    fn edge(&self, i: usize, j: usize) -> (usize, usize) {
        if i < j {
            (i, j)
        } else {
            (j, i)
        }
    }

    fn face(&self, i: usize, j: usize, k: usize) -> [usize; 3] {
        let mut f = [i, j, k];
        f.sort_unstable();
        f
    }

    fn distance(&self, i: usize, j: usize) -> f64 {
        let dx = self.vertices[i][0] - self.vertices[j][0];
        let dy = self.vertices[i][1] - self.vertices[j][1];
        (dx * dx + dy * dy).sqrt()
    }

    fn sample_24(&self, values: &[f64]) -> [f64; 24] {
        let mut out = [0.0_f64; 24];
        if values.is_empty() {
            return out;
        }

        if values.len() == 1 {
            out.fill(values[0]);
            return out;
        }

        let last = (values.len() - 1) as f64;
        for i in 0..24 {
            let pos = (i as f64) * last / 23.0;
            let lo = pos.floor() as usize;
            let hi = pos.ceil() as usize;
            if lo == hi {
                out[i] = values[lo];
            } else {
                let w = pos - (lo as f64);
                out[i] = values[lo] * (1.0 - w) + values[hi] * w;
            }
        }
        out
    }

    fn rand_u64(&mut self) -> u64 {
        // xorshift64* deterministic PRNG
        let mut x = self.rng_state;
        x ^= x >> 12;
        x ^= x << 25;
        x ^= x >> 27;
        self.rng_state = x;
        x.wrapping_mul(0x2545F4914F6CDD1D)
    }

    fn rand_f64(&mut self) -> f64 {
        let v = self.rand_u64() >> 11;
        (v as f64) / ((1u64 << 53) as f64)
    }

    fn rand_sym(&mut self) -> f64 {
        2.0 * self.rand_f64() - 1.0
    }

    fn rand_index(&mut self, upper: usize) -> usize {
        if upper <= 1 {
            0
        } else {
            (self.rand_u64() as usize) % upper
        }
    }

    fn rand_pair(&mut self, upper: usize) -> (usize, usize) {
        let i = self.rand_index(upper);
        let mut j = self.rand_index(upper);
        if i == j {
            j = (j + 1) % upper;
        }
        (i, j)
    }
}
