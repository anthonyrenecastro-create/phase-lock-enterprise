use pyo3::prelude::*;
use pyo3::types::PyDict;

mod engine;

#[pyclass]
pub struct DriftEngine {
    inner: engine::EngineState,
}

#[pymethods]
impl DriftEngine {
    #[new]
    pub fn new(nx: usize, ny: usize, n_fields: usize, seed: u64) -> Self {
        Self {
            inner: engine::EngineState::new(nx, ny, n_fields, seed),
        }
    }

    pub fn stabilize(
        &mut self,
        py: Python<'_>,
        metric_window: Vec<f64>,
        embedding: Option<Vec<f64>>,
    ) -> PyResult<PyObject> {
        if metric_window.is_empty() {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "metric_window must not be empty",
            ));
        }

        let out = self.inner.stabilize(metric_window, embedding);

        let d = PyDict::new(py);
        d.set_item("stabilized_vector", out.stabilized_vector)?;
        d.set_item("drift_score", out.drift_score)?;
        d.set_item("euler_chi", out.euler_chi)?;
        d.set_item("genus", out.genus)?;
        d.set_item("beta0", out.beta0)?;
        d.set_item("beta1", out.beta1)?;
        d.set_item("energy_level", out.energy_level)?;
        d.set_item("stress_level", out.stress_level)?;
        d.set_item("drift_ema", out.drift_ema)?;
        d.set_item("drift_trend", out.drift_trend)?;
        d.set_item("topology_volatility", out.topology_volatility)?;
        d.set_item("surgery_rate", out.surgery_rate)?;
        d.set_item("surgery_total", out.surgery_total)?;
        Ok(d.into())
    }

    pub fn health(&self) -> String {
        "ok".to_string()
    }
}

#[pymodule]
fn phase_lock_core(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    m.add_class::<DriftEngine>()?;
    Ok(())
}
