/* About page: methodology, honest scope, disclaimer. */
export default function About({ health }) {
  const models = health?.models

  return (
    <div className="grid page-enter">
      <div className="panel">
        <div className="panel-head">
          <h2>What this prototype does</h2>
          <span className="panel-note">MonsoonAI version {health?.version || '1.0.0'}</span>
        </div>
        <p>
          Rainfall forecast errors over India are not constant. A model that under-forecasts
          orographic rain over the Western Ghats may over-forecast drizzle during a break spell, so
          a single bias-correction curve fitted to everything averages those situations together and
          fixes neither well.
        </p>
        <p>
          MonsoonAI splits the problem in two. A classifier first decides which weather regime a
          district is in. That decision then routes the raw forecast to a correction model trained
          only on that regime, so each model learns one coherent error pattern. A separate pair of
          calibrated classifiers estimates the probability that the true rainfall reaches heavy or
          very heavy levels, and a verification module scores raw and corrected forecasts side by
          side on a period the models never saw.
        </p>
        <p style={{ marginBottom: 0 }}>
          By default this dashboard is <strong>live</strong>: the raw forecast comes from Open-Meteo,
          a real numerical weather service, for the current forecast cycle. Only the input changes -
          the regime classifier and correction models are the same ones described above, trained
          ahead of time and unchanged at request time. A Demo / Test mode with clearly labelled
          synthetic data is available from the Data source page for offline use or testing.
        </p>
      </div>

      <div className="panel">
        <div className="panel-head"><h2>Live data</h2></div>
        <div className="detail-rows">
          <div className="detail-row"><span>Provider</span><span>Open-Meteo (no API key required)</span></div>
          <div className="detail-row"><span>Update frequency</span><span>Cached up to 10 minutes, or on demand via Refresh</span></div>
          <div className="detail-row"><span>Forecast window</span><span>Next 24 hours from the current time</span></div>
          <div className="detail-row"><span>Verification</span><span>Not available for live forecasts - the window has not occurred yet</span></div>
        </div>
      </div>

      <div className="grid two">
        <div className="panel">
          <div className="panel-head"><h2>Method</h2></div>
          <ul className="tight small">
            <li>
              <strong>Regime classifier.</strong> Random forest over humidity, temperature,
              pressure, wind speed and direction (encoded as sine and cosine), latitude, longitude,
              elevation, distance from coast and cyclical day of year.
            </li>
            <li>
              <strong>Regime-specific correction.</strong> One gradient-boosted regressor per
              regime, trained on the residual (observed minus raw forecast) rather than the absolute
              amount. Predicting the residual means a zero prediction simply returns the raw
              forecast, so the system degrades gracefully. Output is clipped at zero.
            </li>
            <li>
              <strong>Heavy rainfall probability.</strong> Two binary classifiers with isotonic
              calibration, conditioned on the corrected amount. Raw random-forest vote fractions are
              not probabilities, which matters when a number is read as a warning likelihood.
            </li>
            <li>
              <strong>Verification.</strong> RMSE, MAE and bias for amounts; POD, FAR, CSI and ETS
              for events at configurable thresholds; a neighbourhood fractions skill score for
              spatial agreement.
            </li>
          </ul>
        </div>
        <div className="panel">
          <div className="panel-head"><h2>Limits of this build</h2></div>
          <ul className="tight small">
            <li>Demo data is synthetic. Regime labels come from this project's own generative process, not from official meteorological classification.</li>
            <li>Rainfall category thresholds follow widely published operational-style classes but should be verified against the relevant official standard before any operational use.</li>
            <li>FSS is a simplified district-neighbourhood implementation, not a gridded neighbourhood computation.</li>
            <li>Risk bands on the heavy rainfall page are a prototype reading aid, not warning criteria.</li>
            <li>The heavy-rainfall models see in-sample corrected amounts during training, which flatters their calibration slightly.</li>
            <li>District geography in the demo table is approximate.</li>
          </ul>
        </div>
      </div>

      {models ? (
        <div className="panel">
          <div className="panel-head">
            <h2>Loaded models</h2>
            <span className="panel-note">
              mode: <span className="mono">{models.mode}</span>
            </span>
          </div>
          <div className="detail-rows">
            <div className="detail-row">
              <span>Regime classifier</span>
              <span>{models.regime_classifier_loaded ? 'loaded' : 'not trained'}</span>
            </div>
            <div className="detail-row">
              <span>Regime correction models</span>
              <span>{models.regime_correction_models?.length || 0}</span>
            </div>
            <div className="detail-row">
              <span>Heavy rainfall probability</span>
              <span>{models.heavy_probability_model_loaded ? 'loaded' : 'not trained'}</span>
            </div>
            <div className="detail-row">
              <span>Very heavy probability</span>
              <span>{models.very_heavy_probability_model_loaded ? 'loaded' : 'not trained'}</span>
            </div>
            <div className="detail-row">
              <span>Districts loaded</span>
              <span>{health?.districts_loaded ?? '-'}</span>
            </div>
          </div>
        </div>
      ) : null}

      <div className="banner">
        <div>
          <strong>Disclaimer</strong>
          <div>
            This prototype is intended for research and hackathon demonstration. Demo forecasts are
            synthetic and are not official weather forecasts. Real operational deployment requires
            validated NWP forecasts, quality-controlled observations, appropriate regime
            definitions, spatial and temporal validation, calibration, and collaboration with
            meteorological experts.
          </div>
        </div>
      </div>
    </div>
  )
}
