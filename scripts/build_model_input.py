from pathlib import Path
import csv
import hashlib
import numpy as np
import pandas as pd

BASE=Path(__file__).resolve().parent
PAPER=BASE.parents[1]
DTA=PAPER/"data/UKDA-8971-stata/stata/stata13/dcms_csbs_combined_2016-2022_banded_cost_data_only_v3_public.dta"
WEIGHTS=BASE/"G1F_COMMON12_WEIGHT_CROSSWALK.csv"
FOLDS=BASE/"G1F_CV_FOLDS_REPEATED.csv"
G1E=PAPER/"4_Methodology_Design/G1_8971_Audit/G1E_INTEGRATED_ARCHITECTURE"
TLOOKUP=PAPER/"4_Methodology_Design/G1_8971_Audit/CEDB_BPE_LAGGED_THREAT_FEASIBILITY.csv"

P_ITEMS=["rules2","rules3","rules4","rules5","rules7","rules13","rules14","rules15","manage3","ident4"]
PRIMARY_OUTCOME=[f"outcome{i}" for i in [1,2,3,4,5,6,8]]
SECONDARY_IMPACT=[f"impact{i}" for i in [1,2,3,4,7,8,9,10,13,14]]

def sha(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):
            h.update(b)
    return h.hexdigest()

const={}
with open(G1E/"G1E_TRANSFORM_CONSTANTS.csv",encoding="utf-8") as f:
    for row in csv.DictReader(f):
        const[row["constant"]]=float(row["value"])

df=pd.read_stata(DTA,convert_categoricals=False)
df["target_year"]=df.year.map({4:2019,5:2020,7:2022})
d=df[
    (df.questtype==1)
    & df.target_year.isin([2019,2020,2022])
    & df.sector_comb2.isin(range(1,13))
    & df.sizeb.isin([1,2,3])
].copy()
d["uniqser_key"]=d.uniqser.astype(str)

for v in ["online4","online5","online9"]:
    d["E_"+v]=d[v].where(d[v].isin([0,1]))
d["E_mobile"]=d.mobile.map({1:1,2:0})
for v in P_ITEMS:
    d["P_"+v]=d[v].where(d[v].isin([0,1]))

e_cols=["E_online4","E_online5","E_online9","E_mobile"]
p_cols=["P_"+v for v in P_ITEMS]
required=e_cols+p_cols+["sector_comb2","target_year","sizeb"]
x=d[d[required].notna().all(axis=1)].copy()

x["E"]=x[e_cols].mean(axis=1)
x["P_technical_protection"]=x[["P_rules2","P_rules3"]].mean(axis=1)
x["P_access_device_control"]=x[["P_rules4","P_rules7"]].mean(axis=1)
x["P_monitoring"]=x["P_rules5"]
x["P_backup_resilience"]=x[["P_rules13","P_rules14"]].max(axis=1)
x["P_data_governance"]=x["P_rules15"]
x["P_formal_governance"]=x["P_manage3"]
x["P_risk_management"]=x["P_ident4"]
p_domains=[
    "P_technical_protection","P_access_device_control","P_monitoring",
    "P_backup_resilience","P_data_governance","P_formal_governance",
    "P_risk_management"
]
x["P_domain"]=x[p_domains].mean(axis=1)
x["control_count"]=x[p_cols].sum(axis=1)

w=pd.read_csv(WEIGHTS,dtype={"uniqser":str}).rename(columns={"uniqser":"uniqser_key"})
x=x.merge(w,on=["uniqser_key","target_year"],how="left",validate="one_to_one")
missing=x.analysis_weight_common12.isna()
if missing.any():
    excluded=x.loc[missing,["uniqser_key","target_year","weight"]]
    assert len(excluded)==1
    assert int(excluded.iloc[0].target_year)==2019
    assert float(excluded.iloc[0].weight)==0.0
    x=x.loc[~missing].copy()
assert x.analysis_weight_common12.notna().all()

t=pd.read_csv(TLOOKUP)
t=t[t.target_year.isin([2019,2020,2021,2022])].copy()
t["T_log"]=np.log1p(t.lagged_cedb_events.astype(float))
t["T_sector_mean"]=t.groupby("csbs_sector").T_log.transform("mean")
t["T_within"]=t.T_log-t.T_sector_mean
t["T"]=t.T_within/const["T_within_scale"]
tm=t[["csbs_sector","target_year","T"]].rename(columns={"csbs_sector":"sector_comb2"})
x=x.merge(tm,on=["sector_comb2","target_year"],how="left",validate="many_to_one")
assert x["T"].notna().all()

x["E_c"]=x.E-const["E_center"]
x["P_c"]=x.P_domain-const["P_center"]
x["C_c"]=x.control_count-const["control_count_center"]

x["attack_routed_q56a"]=x.outcome1.isin([0,1])
assert (x.attack_routed_q56a==x.impact1.isin([0,1])).all()
x["primary_unknown"]=x.outcome9.eq(1)
x["Y_material_core"]=x[PRIMARY_OUTCOME].eq(1).any(axis=1).astype(int)
x["impact_unknown"]=x.impact12.eq(1)
x["Y_operational_impact"]=x[SECONDARY_IMPACT].eq(1).any(axis=1).astype(int)
x["common_type_any"]=x[[f"type{i}" for i in range(1,10)]].eq(1).any(axis=1)
x["later_type_any"]=x[["type15","type16"]].eq(1).any(axis=1)
x["later_only_attack_2022"]=(
    x.target_year.eq(2022)
    & x.attack_routed_q56a
    & x.later_type_any
    & ~x.common_type_any
)

primary=x[x.attack_routed_q56a & ~x.primary_unknown].copy()

target_total=float(primary.analysis_weight_common12.sum()/primary.target_year.nunique())
primary["analysis_weight_equal_year"]=primary.analysis_weight_common12.astype(float)
primary["annual_method_weight_equal_year"]=primary.sensitivity_weight_annual_method.astype(float)
for year,g in primary.groupby("target_year"):
    idx=g.index
    primary.loc[idx,"analysis_weight_equal_year"] *= target_total/g.analysis_weight_common12.sum()
    primary.loc[idx,"annual_method_weight_equal_year"] *= target_total/g.sensitivity_weight_annual_method.sum()
primary["row_unweighted"]=1.0

assert np.allclose(
    primary.groupby("target_year").analysis_weight_equal_year.sum().to_numpy(),
    target_total,
    rtol=0,
    atol=1e-10,
)
assert np.allclose(
    primary.groupby("target_year").annual_method_weight_equal_year.sum().to_numpy(),
    target_total,
    rtol=0,
    atol=1e-10,
)

out=primary[[
    "uniqser_key","target_year","sector_comb2","sizeb",
    "Y_material_core","Y_operational_impact",
    "E","E_c","P_domain","P_c","control_count","C_c","T",
    "analysis_weight_equal_year","annual_method_weight_equal_year",
    "row_unweighted","later_only_attack_2022"
]].copy()
out=out.sort_values(["target_year","uniqser_key"]).reset_index(drop=True)
out.to_csv(BASE/"G1F_OFFICIAL_MODEL_INPUT.csv",index=False)

folds=pd.read_csv(FOLDS,dtype={"uniqser_key":str})
assert set(out.uniqser_key)==set(folds[folds["repeat"]==1].uniqser_key)
assert folds.groupby("repeat").size().nunique()==1

with open(BASE/"G1F_OFFICIAL_MODEL_INPUT_PROVENANCE.csv","w",newline="",encoding="utf-8") as f:
    z=csv.writer(f)
    z.writerow(["source","sha256","role"])
    for p,role in [
        (DTA,"raw Study 8971 source"),
        (WEIGHTS,"frozen within-wave calibration crosswalk"),
        (FOLDS,"frozen ten-repeat cross-validation assignment"),
        (G1E/"G1E_TRANSFORM_CONSTANTS.csv","accepted G1e centers and anchors"),
        (TLOOKUP,"corrected strictly pre-fieldwork sector event context"),
    ]:
        z.writerow([str(p.relative_to(PAPER)),sha(p),role])
    z.writerow([
        "4_Methodology_Design/G1f_Statistical_Implementation/G1F_OFFICIAL_MODEL_INPUT.csv",
        sha(BASE/"G1F_OFFICIAL_MODEL_INPUT.csv"),
        "derived official conditional analysis input",
    ])

print("OFFICIAL_MODEL_INPUT_BUILD_PASS")
print("n",len(out),"events",int(out.Y_material_core.sum()))
print("year_n",out.groupby("target_year").size().to_dict())
print("equal_year_weight_sums",out.groupby("target_year").analysis_weight_equal_year.sum().to_dict())
print("input_sha256",sha(BASE/"G1F_OFFICIAL_MODEL_INPUT.csv"))
