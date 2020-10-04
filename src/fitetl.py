from wahooreader import WahooTickrX
import os
from pathlib import Path
import pandas as pd
import dask
import glob
from dask.diagnostics import ProgressBar


@dask.delayed
def export_hr_sumstat(fit, datadir):
    wtx = WahooTickrX(fit)
    ts = wtx.datets.strftime('%Y-%m-%d-%H%M%S')
    output_file = Path(f'{datadir}{ts}.csv')

    dt = {'timestamp': wtx.datets}
    rec = dict(wtx.heartrate.max()[['60_sec_rec', '120_sec_rec', '180_sec_rec']])
    zone = wtx.get_heartrate_zones()

    df = pd.DataFrame({**rec, **zone}, index=[dt['timestamp']])
    df.to_csv(output_file)


@dask.delayed
def export_hr_ts(fit, datadir):
    wtx = WahooTickrX(fit)
    ts = wtx.datets.strftime('%Y-%m-%d-%H%M%S')
    output_file = Path(f'{datadir}{ts}.csv')
    wtx.heartrate.to_csv(output_file)


def proc_fit(fit_files, func, datadir):
    """
    Given fitfiles, process them if the processed files don't exist.

    :param func: fit file processing function that exports csvs
    :param datadir: directory where csv-s are exported
    :return: None
    """
    out = []
    for fit in fit_files:
        ts = os.path.basename(fit)[:17]
        output_file = Path(f'{datadir}{ts}.csv')

        if not output_file.exists():
            out.append(func(fit, datadir))

    with ProgressBar():
        dask.compute(*out)


if __name__ == '__main__':

    fit_files = glob.glob('/Users/hasannagib/Dropbox/Apps/WahooFitness/*.fit')
    datadir_hrsum = '/Users/hasannagib/Documents/s3stage/wahoo/heartrate_sumstat/'
    datadir_hrts = '/Users/hasannagib/Documents/s3stage/wahoo/heartrate_ts/'

    proc_fit(fit_files, export_hr_sumstat, datadir_hrsum)
    proc_fit(fit_files, export_hr_ts, datadir_hrts)