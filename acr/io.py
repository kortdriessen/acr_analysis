import pandas as pd
from pathlib import Path
import yaml
import tdt

import kdephys.hypno as kh
import kdephys.pd as kp
import kdephys.xr as kx
import kdephys.utils as ku
import kdephys.ssfm as ss
import ipywidgets as wd
import acr.subjects as asub
import ecephys.hypnogram as eh

import acr

import plotly.express as px
import plotly.io as pio

pio.templates.default = "plotly_dark"

bands = ku.spectral.bands


def acr_path(sub, x):
    path = "/Volumes/opto_loc/Data/" + sub + "/" + sub + "-" + x
    return path


def get_acr_paths(sub, xl):
    paths = {}
    for x in xl:
        path = acr_path(sub, x)
        paths[x] = path
    return paths


def load_subject_data(info, stores=["EEGr", "LFP_"]):
    data = {}
    for exp in info["complete_key_list"]:
        t1 = info["load_times"][exp][0]
        t2 = info["load_times"][exp][1]
        for store in stores:
            chans = info["channels"][store]
            data[exp + "-" + store] = kx.io.get_data(
                info["paths"][exp], store, t1=t1, t2=t2, channel=chans
            )
    return data


def xarray_to_pandas(xarr, name=None):
    if name is None:
        return xarr.to_dataframe()
    else:
        return xarr.to_dataframe(name=name)


def redo_timdelta(df):
    start = df.index.get_level_values(0)[0]
    df.drop(columns=["timedelta"], inplace=True)
    df["timedelta"] = df.index.get_level_values(0) - start
    return df


def check_hypno(subject, condition):
    hypnograms_yaml_file = (
        "/Volumes/opto_loc/Data/ACR_PROJECT_MATERIALS/acr-hypno-paths.yaml"
    )
    with open(hypnograms_yaml_file) as fp:
        yaml_data = yaml.safe_load(fp)
    root = Path(yaml_data[subject]["hypno-root"])
    if condition in yaml_data[subject].keys():
        return True
    else:
        return False


def _load_hypno(subject, condition, start_time):
    hypnograms_yaml_file = (
        "/Volumes/opto_loc/Data/ACR_PROJECT_MATERIALS/acr-hypno-paths.yaml"
    )
    with open(hypnograms_yaml_file) as fp:
        yaml_data = yaml.safe_load(fp)
    root = Path(yaml_data[subject]["hypno-root"])
    if check_hypno(subject, condition):
        hypnogram_fnames = yaml_data[subject][condition]
        hypnogram_paths = [root / (fname + ".txt") for fname in hypnogram_fnames]
        hypnos = range(1, len(hypnogram_paths) + 1)
        hyp_list = []
        for num, hp in zip(hypnos, hypnogram_paths):
            if num == 1:
                h = kh.load_hypno_file(hp, start_time)
                hyp_list.append(h)
            if num > 1:
                h = kh.load_hypno_file(hp, h.end_time.max())
                hyp_list.append(h)
        hh = pd.concat(hyp_list).reset_index(drop=True)
        return hh
    else:
        return None


def load_hypno(info, data, data_tag="EEGr"):
    """
    info --> subject info dictionary
    data --> data dictionary
    Note: The minimum datetime of the data will be taken as the start time for the hypnogram.
    """
    hyp = {}
    subject = info["subject"]
    for cond in info["complete_key_list"]:
        if check_hypno(subject, cond):
            cond_data = cond + "-" + data_tag
            for d in data.keys():
                if cond_data in d:
                    start_time = data[d].datetime.values.min()
                    break
            hyp[cond] = _load_hypno(subject, cond, start_time)
        else:
            print("No hypnogram for condition: ", cond)
    return hyp


def add_hypnograms_to_dataset(dataset, hypno_set):
    for key in hypno_set.keys():
        for exp in dataset.keys():
            if key in exp:
                dataset[exp] = kh.add_states(dataset[exp], hypno_set[key])
    return dataset


def get_spectral(data, hyp, bp_def=bands):
    spg = kx.spectral.get_spg_from_dataset(data)
    # spg = add_hypnograms_to_dataset(spg, hyp)
    bp = {}
    for key in list(spg.keys()):
        bp[key] = kx.spectral.get_bp_set(spg[key], bp_def)
    # bp = add_hypnograms_to_dataset(bp, hyp)
    return spg, bp


def dataset_to_pandas(dataset, name=None):
    for key in list(dataset.keys()):
        dataset[key] = xarray_to_pandas(dataset[key], name=name)
        dataset[key] = redo_timdelta(dataset[key])
        dataset[key]["condition"] = key
        dataset[key] = dataset[key].reset_index()
    return dataset


def load_saved_dataset(si, data_tag, type):
    """
    data_tage --> e.g. '-EEGr'
    type --> e.g. '-spg'
    """
    # TODO: probably needs an update to include the store (-EEGr, NNXr, etc.)
    # TODO: should probably import the data as my pandas ecdata class

    cond_list = si["complete_key_list"]
    sub = si["subject"]
    path_root = (
        "/Volumes/opto_loc/Data/ACR_PROJECT_MATERIALS/" + sub + "/" + "analysis-data/"
    )
    ds = {}
    for cond in cond_list:
        path = path_root + cond + type + ".pkl"
        ds[cond] = pd.read_pickle(path)
    return ds


def save_dataframes(df_dict, si, type="-bp"):
    sub = si["subject"]
    save_path = (
        "/Volumes/opto_loc/Data/ACR_PROJECT_MATERIALS/" + sub + "/" + "analysis-data/"
    )
    for key in list(df_dict.keys()):
        df_dict[key].to_pickle(save_path + key + type + ".pkl")
        print(f"{key} saved")
    return None


def ss_times(sub, exp, print_=False):
    # TODO: this may be deprecated, and may not be needed, I think it was only used for ACR_9?

    # Load the relevant times:
    def acr_get_times(sub, exp):
        block_path = "/Volumes/opto_loc/Data/" + sub + "/" + sub + "-" + exp
        ep = tdt.read_block(block_path, t1=0, t2=0, evtype=["epocs"])
        times = {}
        times["bl_sleep_start"] = ep.epocs.Bttn.onset[0]
        times["stim_on"] = ep.epocs.Wdr_.onset[-1]
        times["stim_off"] = ep.epocs.Wdr_.offset[-1]
        dt_start = pd.to_datetime(ep.info.start_date)

        # This get us the datetime values of the stims for later use:
        on_sec = pd.to_timedelta(times["stim_on"], unit="S")
        off_sec = pd.to_timedelta(times["stim_off"], unit="S")
        times["stim_on_dt"] = dt_start + on_sec
        times["stim_off_dt"] = dt_start + off_sec
        return times

    times = acr_get_times(sub, exp)

    # Start time for scoring is 30 seconds before the button signal was given to inidicate the start of bl peak period.
    start1 = times["bl_sleep_start"] - 30
    end1 = start1 + 7200

    # End time for the second scoring file is when the stim/laser signal is turned off.
    start2 = end1
    end2 = times["stim_off"]
    if print_:
        print("FILE #1"), print(start1), print(end1)
        print("FILE #2"), print(start2), print(end2)
    print("Done loading times")
    return times


def acr_load_master(info, type="pandas", stores=["EEGr", "LFP_"]):
    """
    returns: dataset, spg_set, bp_set, hypno_set.
    hypno_sets is only the mannually scored hypnograms.

    Parameters:
    -----------
    info --> subject info dictionary, ALL RELEVANT INFORMATION IS DEFINED HERE!
    type --> 'pandas' or 'xarray'
    """

    # Load the data
    data = load_subject_data(info, stores=stores)

    # Load the hypnograms
    hyp = load_hypno(info, data)

    # Add the hypnograms to the data
    data = add_hypnograms_to_dataset(data, hyp)

    # Calculate the spectral data
    spg, bp = get_spectral(data, hyp)

    if type == "xarray":
        return data, spg, bp, hyp
    elif type == "pandas":
        data = dataset_to_pandas(data, name="data")
        spg = dataset_to_pandas(spg, name="spg")
        bp = dataset_to_pandas(bp)
        return data, spg, bp, hyp
