import pandas as pd
import yaml
import acr
import tdt
import numpy as np

raw_data_root = "/Volumes/neuropixel_archive/Data/acr_archive/"
materials_root = "/Volumes/opto_loc/Data/ACR_PROJECT_MATERIALS/"
opto_loc_root = "/Volumes/opto_loc/Data/"

swi_subs_exps = {
    "ACR_14": ["swi"],
    "ACR_16": ["swi", "swi2"],
    "ACR_17": ["swi"],
    "ACR_18": ["swi", "swisin"],
    "ACR_19": ["swi", "swi2", "swisin"],
    "ACR_20": ["swi", "swisin"],
    "ACR_21": ["swi", "swi2", "swisin"],
    "ACR_23": ["swi", "swi2", "swisin"],
    "ACR_25": ["swi", "swisin"],
    "ACR_26": ["swi"],
}

sub_probe_locations = {
    "ACR_14": "frontal",
    "ACR_16": "frontal",
    "ACR_17": "parietal",
    "ACR_18": "frontal",
    "ACR_19": "frontal",
    "ACR_20": "frontal",
    "ACR_21": "frontal",
    "ACR_23": "parietal",
    "ACR_25": "frontal",
    "ACR_26": "parietal",
}

sub_exp_types = {
    "ACR_14": "acr",
    "ACR_16": "acr",
    "ACR_17": "acr",
    "ACR_18": "acr",
    "ACR_19": "acr",
    "ACR_20": "acr",
    "ACR_21": "control",
    "ACR_23": "acr",
    "ACR_25": "som",
    "ACR_26": "som",
}


def add_time_class(df, times):
    if "control1" in df.condition[0]:
        stim_on = times["control1"]["stim_on_dt"]
        stim_off = times["control1"]["stim_off_dt"]
    elif "laser1" in df.condition[0]:
        stim_on = times["laser1"]["stim_on_dt"]
        stim_off = times["laser1"]["stim_off_dt"]
    df["time_class"] = "NA"
    df.loc[df.datetime.between(df.datetime.min(), stim_on), "time_class"] = "Baseline"
    stim_mid = stim_on + pd.Timedelta("2H")
    df.loc[df.datetime.between(stim_on, stim_mid), "time_class"] = "Photostim, 0-2Hr"
    df.loc[df.datetime.between(stim_mid, stim_off), "time_class"] = "Photostim, 2-4Hr"
    c1 = stim_off + pd.Timedelta("2H")
    c2 = stim_off + pd.Timedelta("4H")
    c3 = stim_off + pd.Timedelta("6H")
    df.loc[df.datetime.between(stim_off, c1), "time_class"] = "Post Stim, 0-2Hr"
    df.loc[df.datetime.between(c1, c2), "time_class"] = "Post Stim, 2-4Hr"
    df.loc[df.datetime.between(c2, c3), "time_class"] = "Post Stim, 4-6Hr"
    return df


def tdt_to_dt(info, data, time_key, slc=True):
    """converts tdt time to datetime"""

    start = data.datetime.values.min()
    tmin = data.time.values.min()
    dt_start = pd.to_timedelta((info["times"][time_key][0] - tmin), unit="s") + start
    dt_end = pd.to_timedelta((info["times"][time_key][1] - tmin), unit="s") + start
    if slc:
        return slice(dt_start, dt_end)
    else:
        return (dt_start, dt_end)


def get_rec_times(si):
    sub = si["subject"]
    times = {}
    for exp in si["complete_key_list"]:
        p = acr.io.acr_path(sub, exp)
        d = tdt.read_block(p, t1=0, t2=1, evtype=["scalars"])
        i = d.info
        start = np.datetime64(i.start_date)
        end = np.datetime64(i.stop_date)
        d = (end - start) / np.timedelta64(1, "s")
        times[exp] = (start, end, d)
    return times

def elimate_bad_channels(subject, exp, stores=['NNXo', 'NNXr'], fp=True, bp=True, unit_df=True):
    """

    Parameters
    ----------
    subject : _type_
        _description_
    exp : _type_
        _description_
    stores : list, optional
        _description_, by default ['NNXo', 'NNXr']
    fp : bool, optional
        _description_, by default True
    bp : bool, optional
        _description_, by default True
    unit_df : bool, optional
        _description_, by default True
    """
    path = '/Volumes/opto_loc/Data/ACR_PROJECT_MATERIALS/channel_exclusion.yaml'
    params = acr.info_pipeline.subject_params(subject)
    all_chans = params['channels'][stores[0]]
    with open(path, 'r') as f:
        channel_exclusion = yaml.safe_load(f)
    chans_to_exclude = channel_exclusion[subject][exp]
    chans_to_keep = [chan for chan in all_chans if chan not in chans_to_exclude]
    recordings = acr.info_pipeline.get_exp_recs(subject, exp)
