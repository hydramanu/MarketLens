# Example research note: Apple historical study

Selected window: **2016-02-19 to 2017-02-16**, 252 daily observations from the Plotly public Apple example dataset. This is a historical learning exercise, not a current market assessment.

1. **Price return was +40.93%.** The last raw close was $135.35. This measures the change between window endpoints and excludes dividends, transaction costs and taxes.
2. **Latest rolling annualized volatility was 22.17%.** This uses the final 20 close-to-close returns, sample standard deviation and sqrt(252). It describes observed variability, not the probability of a future outcome.
3. **Maximum drawdown was −19.41%.** A positive endpoint return still included a substantial decline from an earlier in-window peak. Peaks before the selected start are not considered.
4. **The historical 95% daily loss threshold was 2.08%, with a 2.75% tail mean loss.** These are empirical summaries of 251 returns; losses can exceed them. Small samples and changing market conditions limit their usefulness.
5. **The cleaning step retained all 506 source rows, and the selected window had no gaps longer than four calendar days.** This does not prove accuracy or completeness: no official exchange calendar or corporate-action feed was checked.

Window receipt SHA-256: `67303c631d4b18a1a4024005fecbbe0006059f93ff6ecf1dc9f429d3824fcb78`. Method version: `1.0.0`.

Reproduce by selecting Apple, 252 observations, and replay through 2017-02-16. Use **Download research brief** to generate observations for another window. The source dataset is downloaded at runtime and may change upstream; compare the receipt before claiming an exact reproduction.

## What this study does not establish

It does not establish why prices changed, future returns, the performance of the entire S&P 500, or the suitability of any investment. The dashboard's crypto feed is a separate demonstration of current public market-data ingestion, not an update of this historical stock dataset.
