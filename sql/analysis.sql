-- Parameterized by the service. LAG makes the previous observation explicit.
WITH daily AS (
  SELECT date, close, volume,
    LAG(close) OVER (ORDER BY date) AS previous_close,
    LAG(volume) OVER (ORDER BY date) AS previous_volume
  FROM prices WHERE dataset = ? AND date <= ?
)
SELECT date, close, volume,
  ROUND(100.0 * (close / previous_close - 1), 4) AS return_pct,
  ROUND(100.0 * (volume / NULLIF(previous_volume, 0) - 1), 4) AS volume_change_pct
FROM daily ORDER BY date DESC LIMIT 15;
