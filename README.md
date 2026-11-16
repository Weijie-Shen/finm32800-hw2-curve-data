# HW2 Treasury curve data for FINM 32800 issue 93

This `report-data` branch publishes derived data only. It contains no raw quotes,
CUSIPs, credentials, or graded homework solutions. The report reads it as a pinned
ChartBook 0.5 git dependency; no build script or WRDS access is needed by readers.

## Provenance and committed scope

Author: Weijie-Shen. Upstream: the private HW2 repository, original commit
`20f5b892cdc482d4b2b64a45e87a55b18463ce6e`, with the report-specific exporter
`src/export_report_curves.py` at commit `f9f689f` on branch
`report/treasury_curve_fit`. Original homework code and tests are unchanged.
The three fixed cross-sections are 2026-03-31, 2026-06-30, and 2026-09-30;
END_DATE is 2026-09-30. These constants are committed in the exporter, never
read from `.env`. There is no automatic refresh.

The HW2 CRSP Treasury pull reads notes and bonds through WRDS and constructs dirty
mid-prices and semiannual cashflows. Its filters remove short maturities,
on/first-off-the-run issues, callable bonds, and the excluded 20-year issues.
The resulting sample has 300 bonds on each date. Licensed source records remain
private. No Fed yields or Fed parameters enter fitting or selection.

## Estimation

Minimize mean((dirty observed price - discounted cashflows)^2 / duration),
using the HW2 continuously compounded Nelson-Siegel-Svensson implementation.
Parameter order is tau1, tau2, beta1, beta2, beta3, beta4. Betas are decimal rates.
To avoid the pilot's large cancelling coefficients and negative asymptotic yields,
tau1/tau2 are bounded to [0.1,30] years, beta1 to [0,0.15], and the other betas
to [-0.3,0.3]. These are numerical regularity choices, not estimates from the Fed.
A sensitivity run expands the tau upper limit to 50 and the latter beta bounds to
[-0.6,0.6]. Both use 14 predetermined starts, SciPy least_squares with complex-step
Jacobian, tolerances 1e-12, and a 3000-evaluation limit. The successful run with the
lowest price objective is selected. All 14 starts converge on each date; multiple
starts reach the selected minimum. This does not prove a global minimum.

Some selected parameters reach bounds, including the asymptotic level at zero;
parameters should not be interpreted structurally and curves should not be
extrapolated beyond the displayed 1-30 years. Widening the bounds changes displayed
yields by at most 0.203 basis points. These are constrained HW2 extensions, not an
exact reproduction of the Fed's estimation methodology. Benchmark gaps do not
establish security mispricing or explain policy expectations versus term premiums.

## Files and units

- `treasury_curve_fits.csv`: 90 unique date/maturity rows, continuously compounded
  yields in percent. One percent corresponds to 100 basis points. The sensitivity
  column is the wider-bound fit, not a confidence interval.
- `fit_diagnostics.csv`: three aggregate diagnostic rows; the objective is a
  duration-weighted squared price error, not a yield RMSE.

Regenerate privately in the HW2 finm environment with
`python src/export_report_curves.py --cache-dir _data/report_curves --output-dir _output/report_curves`.
The exporter retrieves missing dates with the existing WRDS pull and uses the
same committed settings for all machines. Vendors can revise historical data;
this public branch freezes the actual derived CSV bytes, and the report locks
both their hashes and this branch's commit. Publish a new commit to revise data.

Method reference: Gurkaynak, Sack, and Wright (2007), The U.S. Treasury Yield
Curve: 1961 to the Present, Journal of Monetary Economics 54, 2291-2304.
