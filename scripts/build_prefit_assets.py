from pathlib import Path
import csv, hashlib, json, math
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
RESCUE=HERE.parent
PAPER=RESCUE.parents[1]
INPUTS=RESCUE/"03_Inputs"
GATES=RESCUE/"01_Gates"
Q0=RESCUE/"00_Q0"
for p in [INPUTS,GATES,Q0]:
    p.mkdir(parents=True,exist_ok=True)

D8971=PAPER/"data/UKDA-8971-stata/stata/stata13/dcms_csbs_combined_2016-2022_banded_cost_data_only_v3_public.dta"
D2023=PAPER/"data/UKDA-9101-stata/stata/stata13/csbs_2023_22-034904-01_banded_cost_data_v6-1_public.dta"
D2024=PAPER/"data/UKDA-9285-stata/stata/stata13/csbs_2024_archive_data_public.dta"
D2025=PAPER/"data/UKDA-9404-stata/stata/stata13/csbs_2025_archive_data_public.dta"
DCSLS=PAPER/"data/UKDA-9356-stata/stata/stata13/csls_waves_1-4.dta"
G1F=PAPER/"4_Methodology_Design/G1f_Statistical_Implementation"
G1E=PAPER/"4_Methodology_Design/G1_8971_Audit/G1E_INTEGRATED_ARCHITECTURE"
WEIGHTS=G1F/"G1F_COMMON12_WEIGHT_CROSSWALK.csv"
TLOOKUP=PAPER/"4_Methodology_Design/G1_8971_Audit/CEDB_BPE_LAGGED_THREAT_FEASIBILITY.csv"
ATTEMPT3=PAPER/"9_Audit/review_pipeline_20261005_G1f_STATS/00_pipeline/official_fit_attempt3_completed"
P_ITEMS=["rules2","rules3","rules4","rules5","rules7","rules13","rules14","rules15","manage3","ident4"]
PRIMARY_OUTCOME=[f"outcome{i}" for i in [1,2,3,4,5,6,8]]
SECONDARY_IMPACT=[f"impact{i}" for i in [1,2,3,4,7,8,9,10,13,14]]
P_DOMAINS=[
    "P_technical_protection","P_access_device_control","P_monitoring",
    "P_backup_resilience","P_data_governance","P_formal_governance",
    "P_risk_management"
]

def sha(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):
            h.update(b)
    return h.hexdigest()

def weighted_quantile(values,weights,q):
    x=np.asarray(values,float); w=np.asarray(weights,float)
    ok=np.isfinite(x)&np.isfinite(w)&(w>0)
    x=x[ok]; w=w[ok]
    order=np.argsort(x)
    x=x[order]; w=w[order]
    c=np.cumsum(w)
    return float(x[np.searchsorted(c,q*c[-1],side="left")])

def equal_year_scale(d,source,target):
    d=d.copy()
    d[target]=d[source].astype(float)
    years=sorted(d.target_year.unique())
    tgt=float(d[source].sum()/len(years))
    for y,g in d.groupby("target_year"):
        idx=g.index
        d.loc[idx,target]*=tgt/g[source].sum()
    return d

def design_matrix(d,continuous,catcols):
    parts=[np.ones((len(d),1))]
    names=["Intercept"]
    for c in continuous:
        parts.append(d[[c]].to_numpy(float)); names.append(c)
    for c in catcols:
        z=pd.get_dummies(d[c].astype(int).astype(str),prefix=c,drop_first=True,dtype=float)
        parts.append(z.to_numpy(float)); names.extend(z.columns.tolist())
    X=np.column_stack(parts)
    return X,names

def write_json(path,obj):
    Path(path).write_text(json.dumps(obj,indent=2,sort_keys=True),encoding="utf-8")

def category_crosswalk(path,dataset,variables):
    raw=pd.read_stata(path,convert_categoricals=False)
    cat=pd.read_stata(path,convert_categoricals=True)
    labs=pd.io.stata.StataReader(path).variable_labels()
    rows=[]
    for v in variables:
        if v not in raw.columns:
            rows.append({"dataset":dataset,"variable":v,"variable_label":"","raw_code":"","category_label":"","status":"MISSING"})
            continue
        tmp=pd.DataFrame({"raw":raw[v],"cat":cat[v].astype(object)})
        tmp=tmp.drop_duplicates()
        for _,r in tmp.iterrows():
            rv=r["raw"]; cv=r["cat"]
            rows.append({
                "dataset":dataset,"variable":v,"variable_label":labs.get(v,""),
                "raw_code":"" if pd.isna(rv) else rv,
                "category_label":"" if pd.isna(cv) else str(cv),
                "status":"PRESENT"
            })
    return rows

# ---------------- Q0 hashes ----------------
hash_targets=[
    (D8971,"raw Study 8971"),
    (D2023,"raw CSBS 2023 Study 9101"),
    (D2024,"raw CSBS 2024 Study 9285"),
    (D2025,"raw CSBS 2025 Study 9404"),
    (DCSLS,"raw CSLS Study 9356"),
    (G1F/"G1F_OFFICIAL_MODEL_INPUT.csv","frozen G1f model input"),
    (G1F/"G1F_CV_FOLDS_REPEATED.csv","frozen G1f CV folds"),
    (G1E/"G1E_TRANSFORM_CONSTANTS.csv","frozen G1e constants"),
    (WEIGHTS,"frozen G1f weight crosswalk"),
    (TLOOKUP,"frozen lagged context lookup"),
    (ATTEMPT3/"result_artifact_sha256.txt","frozen G1f attempt3 result manifest"),
]
with open(Q0/"Q0_INPUT_HASH_MANIFEST.csv","w",newline="",encoding="utf-8") as f:
    w=csv.writer(f); w.writerow(["path","sha256","role"])
    for p,role in hash_targets:
        w.writerow([str(p.relative_to(PAPER)),sha(p),role])

# ---------------- Study 8971 base for E1-E5/E8 ----------------
const={}
with open(G1E/"G1E_TRANSFORM_CONSTANTS.csv",encoding="utf-8") as f:
    for row in csv.DictReader(f):
        const[row["constant"]]=float(row["value"])

df=pd.read_stata(D8971,convert_categoricals=False)
df["target_year"]=df.year.map({4:2019,5:2020,7:2022})
d=df[
    (df.questtype==1)&df.target_year.isin([2019,2020,2022])
    &df.sector_comb2.isin(range(1,13))&df.sizeb.isin([1,2,3])
].copy()
d["uniqser_key"]=d.uniqser.astype(str)
for v in ["online4","online5","online9"]:
    d["E_"+v]=d[v].where(d[v].isin([0,1]))
d["E_mobile"]=d.mobile.map({1:1,2:0})
for v in P_ITEMS:
    d["P_"+v]=d[v].where(d[v].isin([0,1]))
e_cols=["E_online4","E_online5","E_online9","E_mobile"]
p_cols=["P_"+v for v in P_ITEMS]
x=d[d[e_cols+p_cols+["sector_comb2","target_year","sizeb"]].notna().all(axis=1)].copy()
x["E"]=x[e_cols].mean(axis=1)
x["P_technical_protection"]=x[["P_rules2","P_rules3"]].mean(axis=1)
x["P_access_device_control"]=x[["P_rules4","P_rules7"]].mean(axis=1)
x["P_monitoring"]=x["P_rules5"]
x["P_backup_resilience"]=x[["P_rules13","P_rules14"]].max(axis=1)
x["P_data_governance"]=x["P_rules15"]
x["P_formal_governance"]=x["P_manage3"]
x["P_risk_management"]=x["P_ident4"]
x["P_domain"]=x[P_DOMAINS].mean(axis=1)
x["control_count"]=x[p_cols].sum(axis=1)

w=pd.read_csv(WEIGHTS,dtype={"uniqser":str}).rename(columns={"uniqser":"uniqser_key"})
x=x.merge(w,on=["uniqser_key","target_year"],how="left",validate="one_to_one")
missing=x.analysis_weight_common12.isna()
if missing.any():
    ex=x.loc[missing,["uniqser_key","target_year","weight"]]
    assert len(ex)==1 and int(ex.iloc[0].target_year)==2019 and float(ex.iloc[0].weight)==0.0
    x=x.loc[~missing].copy()

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
x["attack_routed_q56a"]=x.outcome1.isin([0,1]).astype(int)
x["primary_unknown"]=x.outcome9.eq(1)
x["impact_routed_q56a"]=x.impact1.isin([0,1]).astype(int)
x["impact_unknown"]=x.impact12.eq(1)
x["Y_material_core"]=x[PRIMARY_OUTCOME].eq(1).any(axis=1).astype(int)
x["Y_operational_impact"]=x[SECONDARY_IMPACT].eq(1).any(axis=1).astype(int)

x=equal_year_scale(x,"analysis_weight_common12","selection_weight_equal_year")
primary=x[(x.attack_routed_q56a==1)&~x.primary_unknown].copy()
primary=equal_year_scale(primary,"analysis_weight_common12","material_weight_equal_year")
impact=x[(x.impact_routed_q56a==1)&~x.impact_unknown].copy()
impact=equal_year_scale(impact,"analysis_weight_common12","impact_weight_equal_year")

assert len(x)==3544
assert len(primary)==1542
assert int(primary.Y_material_core.sum())==329
assert len(impact)==1553
assert int(impact.Y_operational_impact.sum())==554
assert int(x.attack_routed_q56a.sum())==1555

keep=[
 "uniqser_key","target_year","sector_comb2","sizeb","T",
 *e_cols,*p_cols,*P_DOMAINS,"E","P_domain","control_count","E_c","P_c","C_c",
 "analysis_weight_common12","sensitivity_weight_annual_method","selection_weight_equal_year",
 "attack_routed_q56a","primary_unknown","impact_routed_q56a","impact_unknown",
 "Y_material_core","Y_operational_impact"
]
x[keep].sort_values(["target_year","uniqser_key"]).to_csv(INPUTS/"E1_E5_E8_8971_BASE.csv",index=False)
impact[[c for c in keep if c in impact.columns]+["impact_weight_equal_year"]].sort_values(["target_year","uniqser_key"]).to_csv(INPUTS/"E1_8971_OPERATIONAL_IMPACT_INPUT.csv",index=False)
primary[[c for c in keep if c in primary.columns]+["material_weight_equal_year"]].sort_values(["target_year","uniqser_key"]).to_csv(INPUTS/"E2_E5_8971_MATERIAL_INPUT.csv",index=False)

# E2/E4/E5 prefit ranks and anchors
m6_cont=["E_c","T","P_c","E2","P2","EP"]
def add_m6_terms(z,Ecol="E",Pcol="P_domain",ecenter=None,pcenter=None):
    q=z.copy()
    if ecenter is None: ecenter=float(q[Ecol].mean())
    if pcenter is None: pcenter=float(q[Pcol].mean())
    q["_Ec"]=q[Ecol]-ecenter; q["_Pc"]=q[Pcol]-pcenter
    q["E2"]=q["_Ec"]**2; q["P2"]=q["_Pc"]**2; q["EP"]=q["_Ec"]*q["_Pc"]
    return q

gate8971={"gate_id":"Q0_8971_prefit","verdict":"PASS","checks":{}}
q=primary.copy()
q["E2"]=q.E_c**2; q["P2"]=q.P_c**2; q["EP"]=q.E_c*q.P_c
X,names=design_matrix(q,["E_c","T","P_c","E2","P2","EP"],["sizeb","target_year","sector_comb2"])
gate8971["checks"]["primary_M6"]={"n":len(q),"events":int(q.Y_material_core.sum()),"parameters":X.shape[1],"rank":int(np.linalg.matrix_rank(X)),"full_rank":bool(np.linalg.matrix_rank(X)==X.shape[1]),"events_per_parameter":float(q.Y_material_core.sum()/X.shape[1])}

qi=impact.copy()
qi["E2"]=qi.E_c**2; qi["P2"]=qi.P_c**2; qi["EP"]=qi.E_c*qi.P_c
Xi,_=design_matrix(qi,["E_c","T","P_c","E2","P2","EP"],["sizeb","target_year","sector_comb2"])
gate8971["checks"]["E1_operational_M6"]={"n":len(qi),"events":int(qi.Y_operational_impact.sum()),"parameters":Xi.shape[1],"rank":int(np.linalg.matrix_rank(Xi)),"full_rank":bool(np.linalg.matrix_rank(Xi)==Xi.shape[1]),"events_per_parameter":float(qi.Y_operational_impact.sum()/Xi.shape[1])}

for drop in [2019,2020,2022]:
    z=primary[primary.target_year!=drop].copy()
    z["E2"]=z.E_c**2; z["P2"]=z.P_c**2; z["EP"]=z.E_c*z.P_c
    Xz,_=design_matrix(z,["E_c","T","P_c","E2","P2","EP"],["sizeb","target_year","sector_comb2"])
    gate8971["checks"][f"E2_exclude_{drop}"]={"n":len(z),"events":int(z.Y_material_core.sum()),"parameters":Xz.shape[1],"rank":int(np.linalg.matrix_rank(Xz)),"full_rank":bool(np.linalg.matrix_rank(Xz)==Xz.shape[1]),"events_per_parameter":float(z.Y_material_core.sum()/Xz.shape[1]),"sector_clusters":int(z.sector_comb2.nunique())}

ablation_rows=[]
for evar in e_cols:
    remaining=[c for c in e_cols if c!=evar]
    z=primary.copy()
    z["_Eabl"]=z[remaining].mean(axis=1)
    eq25=weighted_quantile(z["_Eabl"],z.material_weight_equal_year,.25)
    eq75=weighted_quantile(z["_Eabl"],z.material_weight_equal_year,.75)
    ecenter=float(np.average(z["_Eabl"],weights=z.material_weight_equal_year))
    ablation_rows.append({"family":"E_leave_one_out","variant":f"drop_{evar}","removed":evar,"E_center":ecenter,"P_center":const["P_center"],"E_q25":eq25,"E_q75":eq75,"P_q25":const["P_q25"],"P_q75":const["P_q75"],"E_sd":float(z["_Eabl"].std(ddof=1)),"P_sd":float(z.P_domain.std(ddof=1))})
for pdom in P_DOMAINS:
    remaining=[c for c in P_DOMAINS if c!=pdom]
    z=primary.copy()
    z["_Pabl"]=z[remaining].mean(axis=1)
    pq25=weighted_quantile(z["_Pabl"],z.material_weight_equal_year,.25)
    pq75=weighted_quantile(z["_Pabl"],z.material_weight_equal_year,.75)
    pcenter=float(np.average(z["_Pabl"],weights=z.material_weight_equal_year))
    ablation_rows.append({"family":"P_leave_one_out","variant":f"drop_{pdom}","removed":pdom,"E_center":const["E_center"],"P_center":pcenter,"E_q25":const["E_q25"],"E_q75":const["E_q75"],"P_q25":pq25,"P_q75":pq75,"E_sd":float(z.E.std(ddof=1)),"P_sd":float(z["_Pabl"].std(ddof=1))})
pd.DataFrame(ablation_rows).to_csv(INPUTS/"E4_E5_ABLATION_PREFIT_ANCHORS.csv",index=False)

sel=x.copy()
sel["EP"]=sel.E_c*sel.P_c
Xs,_=design_matrix(sel,["E_c","P_c","EP"],["sizeb","target_year","sector_comb2"])
gate8971["checks"]["E8_selection_SEL2"]={"n":len(sel),"routed":int(sel.attack_routed_q56a.sum()),"not_routed":int((1-sel.attack_routed_q56a).sum()),"parameters":Xs.shape[1],"rank":int(np.linalg.matrix_rank(Xs)),"full_rank":bool(np.linalg.matrix_rank(Xs)==Xs.shape[1]),"weighted_routed_share":float(np.average(sel.attack_routed_q56a,weights=sel.selection_weight_equal_year))}
if any(not v.get("full_rank",True) for v in gate8971["checks"].values() if isinstance(v,dict)):
    gate8971["verdict"]="FAIL_REPAIR"
write_json(GATES/"Q0_8971_PREFIT_GATE.json",gate8971)

# ---------------- E6 recent CSBS ----------------
recent=[]
crosswalk=[]
recent_paths={2023:D2023,2024:D2024,2025:D2025}
cwvars=["questtype","sizeb","sector_comb2",*P_ITEMS,*PRIMARY_OUTCOME,"outcome9",*SECONDARY_IMPACT,"impact12","weight"]
for year,path in recent_paths.items():
    crosswalk.extend(category_crosswalk(path,str(year),cwvars))
    dd=pd.read_stata(path,convert_categoricals=False)
    dd=dd[(dd.questtype==1)&dd.sizeb.isin([1,2,3])&dd.sector_comb2.isin(range(1,14))].copy()
    dd["target_year"]=year
    dd["uniqser_key"]=dd.uniqser.astype(str) if "uniqser" in dd else np.arange(len(dd)).astype(str)
    for v in P_ITEMS:
        dd["P_"+v]=dd[v].where(dd[v].isin([0,1]))
    pp=["P_"+v for v in P_ITEMS]
    dd=dd[dd[pp].notna().all(axis=1)].copy()
    dd["P_technical_protection"]=dd[["P_rules2","P_rules3"]].mean(axis=1)
    dd["P_access_device_control"]=dd[["P_rules4","P_rules7"]].mean(axis=1)
    dd["P_monitoring"]=dd["P_rules5"]
    dd["P_backup_resilience"]=dd[["P_rules13","P_rules14"]].max(axis=1)
    dd["P_data_governance"]=dd["P_rules15"]
    dd["P_formal_governance"]=dd["P_manage3"]
    dd["P_risk_management"]=dd["P_ident4"]
    dd["P_domain"]=dd[P_DOMAINS].mean(axis=1)
    dd["control_count"]=dd[pp].sum(axis=1)
    dd["attack_routed_q56a"]=dd.outcome1.isin([0,1]).astype(int)
    dd["primary_unknown"]=dd.outcome9.eq(1)
    dd["impact_routed_q56a"]=dd.impact1.isin([0,1]).astype(int)
    dd["impact_unknown"]=dd.impact12.eq(1)
    dd["Y_material_core"]=dd[PRIMARY_OUTCOME].eq(1).any(axis=1).astype(int)
    dd["Y_operational_impact"]=dd[SECONDARY_IMPACT].eq(1).any(axis=1).astype(int)
    recent.append(dd)
pd.DataFrame(crosswalk).to_csv(Q0/"E6_RECENT_CSBS_CODING_CROSSWALK.csv",index=False)
rall=pd.concat(recent,ignore_index=True)
rall["row_id"]=rall.target_year.astype(str)+"-"+rall.uniqser_key.astype(str)
rall["P_c"]=rall.P_domain-rall.P_domain.mean()
rall["C_c"]=rall.control_count-rall.control_count.mean()
for target,mask in [
    ("routing_weight_equal_year",pd.Series(True,index=rall.index)),
    ("material_weight_equal_year",(rall.attack_routed_q56a==1)&~rall.primary_unknown),
    ("impact_weight_equal_year",(rall.impact_routed_q56a==1)&~rall.impact_unknown),
]:
    rall[target]=np.nan
    sub=rall.loc[mask].copy()
    tgt=float(sub.weight.sum()/sub.target_year.nunique())
    for yy,g in sub.groupby("target_year"):
        idx=g.index
        rall.loc[idx,target]=g.weight.astype(float)*tgt/g.weight.sum()
recent_keep=["row_id","uniqser_key","target_year","sector_comb2","sizeb","weight",*["P_"+v for v in P_ITEMS],*P_DOMAINS,"P_domain","control_count","P_c","C_c","attack_routed_q56a","primary_unknown","impact_routed_q56a","impact_unknown","Y_material_core","Y_operational_impact"]
routing_weight_cols=["routing_weight_equal_year","material_weight_equal_year","impact_weight_equal_year"]
rall[recent_keep+routing_weight_cols].sort_values(["target_year","row_id"]).to_csv(INPUTS/"E6_RECENT_CSBS_BASE.csv",index=False)
rprimary=rall[(rall.attack_routed_q56a==1)&~rall.primary_unknown].copy()
rimpact=rall[(rall.impact_routed_q56a==1)&~rall.impact_unknown].copy()
assert len(rprimary)==2717 and int(rprimary.Y_material_core.sum())==348
assert int(rimpact.Y_operational_impact.sum())==713

# predictor-only constants
e6const={
    "P_center":float(np.average(rprimary.P_domain,weights=rprimary.weight)),
    "P_q25":weighted_quantile(rprimary.P_domain,rprimary.weight,.25),
    "P_q75":weighted_quantile(rprimary.P_domain,rprimary.weight,.75),
    "C_center":float(np.average(rprimary.control_count,weights=rprimary.weight)),
    "primary_n":int(len(rprimary)),"primary_events":int(rprimary.Y_material_core.sum()),
    "impact_n":int(len(rimpact)),"impact_events":int(rimpact.Y_operational_impact.sum())
}
write_json(INPUTS/"E6_PREFIT_CONSTANTS.json",e6const)

def make_folds(d,outcome,prefix):
    parts=[]
    for rep in range(1,11):
        for (year,y),g0 in d.groupby(["target_year",outcome],sort=True):
            g=g0[["row_id","target_year",outcome]].copy()
            seed=f"{prefix}_R{rep:02d}"
            g["_h"]=g.row_id.map(lambda z: hashlib.sha256(f"{seed}|{year}|{int(y)}|{z}".encode()).hexdigest())
            g=g.sort_values(["_h","row_id"]).reset_index(drop=True)
            g["fold"]=(np.arange(len(g))%5)+1
            g["repeat"]=rep
            parts.append(g.drop(columns="_h"))
    return pd.concat(parts,ignore_index=True)

fmat=make_folds(rprimary,"Y_material_core","C1_E6_MATERIAL")
fimp=make_folds(rimpact,"Y_operational_impact","C1_E6_IMPACT")
fmat.to_csv(INPUTS/"E6_MATERIAL_CV_FOLDS.csv",index=False)
fimp.to_csv(INPUTS/"E6_IMPACT_CV_FOLDS.csv",index=False)

gate6={"gate_id":"Q0_E6_G0_G1_G2","verdict":"PASS","checks":{}}
for name,dd,outcome in [("material",rprimary,"Y_material_core"),("impact",rimpact,"Y_operational_impact")]:
    z=dd.copy()
    pc=e6const["P_center"]; cc=e6const["C_center"]
    z["_P"]=z.P_domain-pc; z["_C"]=z.control_count-cc
    z["P2"]=z._P**2; z["C2"]=z._C**2
    XP,_=design_matrix(z,["_P","P2"],["sizeb","target_year","sector_comb2"])
    XC,_=design_matrix(z,["_C","C2"],["sizeb","target_year","sector_comb2"])
    gate6["checks"][name]={
        "n":len(z),"events":int(z[outcome].sum()),"years":int(z.target_year.nunique()),"sectors":int(z.sector_comb2.nunique()),"sizes":int(z.sizeb.nunique()),
        "P_parameters":XP.shape[1],"P_rank":int(np.linalg.matrix_rank(XP)),"P_full_rank":bool(np.linalg.matrix_rank(XP)==XP.shape[1]),
        "C_parameters":XC.shape[1],"C_rank":int(np.linalg.matrix_rank(XC)),"C_full_rank":bool(np.linalg.matrix_rank(XC)==XC.shape[1]),
        "P_sd":float(z.P_domain.std(ddof=1)),"C_sd":float(z.control_count.std(ddof=1))
    }
# fold integrity
for tag,ff,dd in [("material_folds",fmat,rprimary),("impact_folds",fimp,rimpact)]:
    problems=[]
    for rep,g in ff.groupby("repeat"):
        if len(g)!=len(dd) or g.row_id.duplicated().any() or sorted(g.fold.unique())!=[1,2,3,4,5]:
            problems.append(int(rep))
    gate6["checks"][tag]={"repeats":10,"rows_per_repeat":len(dd),"problem_repeats":problems,"pass":not problems}
if not all(v.get("P_full_rank",True) and v.get("C_full_rank",True) and v.get("pass",True) for v in gate6["checks"].values()):
    gate6["verdict"]="FAIL_REPAIR"
write_json(GATES/"Q0_E6_G0_G1_G2_GATE.json",gate6)

# ---------------- E7 CSLS panel ----------------
csls_vars=["LongId","wave","qsize","wght","rulesf","rulesg","rulesh","rulesi","rulesb","rulesd","rulese","rulesc","gov6","identb","onlinea","onlineb","devices","incident12","brk_outcome","brk_impact"]
pd.DataFrame(category_crosswalk(DCSLS,"CSLS_9356",csls_vars)).to_csv(Q0/"E7_CSLS_CODING_CROSSWALK.csv",index=False)
dd=pd.read_stata(DCSLS,convert_categoricals=False).copy()
def yn(s):
    return s.map({1:1.0,2:0.0})
for v in ["rulesf","rulesg","rulesh","rulesi","rulesb","rulesd","rulese","rulesc","identb","onlinea","onlineb","devices"]:
    dd["_"+v]=yn(dd[v])
dd["_gov6"]=dd.gov6.map({1:1.0,2:0.0})
dd["_incident"]=dd.incident12.map({1:1.0,2:0.0})
dd["_outcome"]=dd.brk_outcome.map({1:1.0,2:0.0})
dd["_impact"]=dd.brk_impact.map({1:1.0,2:0.0})
dd["P_technical_protection"]=dd[["_rulesf","_rulesg"]].mean(axis=1,skipna=False)
dd["P_access_device_control"]=dd[["_rulesh","_rulesi"]].mean(axis=1,skipna=False)
dd["P_monitoring"]=dd["_rulesb"]
dd["P_backup_resilience"]=dd[["_rulesd","_rulese"]].max(axis=1,skipna=False)
dd["P_data_governance"]=dd["_rulesc"]
dd["P_formal_governance"]=dd["_gov6"]
dd["P_risk_management"]=dd["_identb"]
dd["P_CSLS_analog"]=dd[P_DOMAINS].mean(axis=1,skipna=False)
dd["E_CSLS"]=dd[["_onlinea","_onlineb","_devices"]].mean(axis=1,skipna=False)

trans=[]
for lid,g in dd.sort_values(["LongId","wave"]).groupby("LongId"):
    by={int(r.wave):r for _,r in g.iterrows() if pd.notna(r.wave)}
    for ww in [1,2,3]:
        if ww not in by or ww+1 not in by: continue
        a=by[ww]; b=by[ww+1]
        if a.qsize!=2: continue
        rec={"LongId":str(lid),"wave_t":ww,"wave_next":ww+1,"transition":f"{ww}_to_{ww+1}","wght_t":a.wght}
        for c in P_DOMAINS:
            rec[c+"_t"]=a[c]
        rec.update({
            "P_t":a.P_CSLS_analog,"E_t":a.E_CSLS,
            "incident_t":a._incident,"material_t":a._outcome,"impact_t":a._impact,
            "P_next":b.P_CSLS_analog,"E_next":b.E_CSLS,
            "incident_next":b._incident,"material_next":b._outcome,"impact_next":b._impact,
        })
        trans.append(rec)
tr=pd.DataFrame(trans)
core_req=["P_t","E_t","P_next","incident_t","material_t","impact_t","incident_next","material_next","impact_next"]
core=tr[tr[core_req].notna().all(axis=1)].copy()
core.to_csv(INPUTS/"E7_CSLS_MEDIUM_TRANSITIONS.csv",index=False)

gate7={"gate_id":"Q0_E7_G0_G1_G2_G3","verdict":"PASS","checks":{}}
p=core.P_t
vc=p.value_counts(normalize=True)
gate7["checks"]["P_variance"]={"n":len(core),"orgs":int(core.LongId.nunique()),"mean":float(p.mean()),"sd":float(p.std(ddof=1)),"distinct":int(p.nunique()),"max_point_share":float(vc.max()),"pass":bool(p.std(ddof=1)>=0.10 and p.nunique()>=8 and vc.max()<=0.60)}
domchecks={}
for c in P_DOMAINS:
    s=core[c+"_t"]
    domchecks[c]={"sd":float(s.std(ddof=1)),"distinct":int(s.nunique()),"pass":bool(s.std(ddof=1)>=0.05 and s.nunique()>=2)}
gate7["checks"]["domain_variance"]=domchecks
# core TQ1 design: intercept, P_t,E_t,prior material, transition dummies
tmp=core.copy()
X7,n7=design_matrix(tmp,["P_t","E_t","material_t"],["wave_t"])
rank7=int(np.linalg.matrix_rank(X7))
gate7["checks"]["TQ1_rank"]={"parameters":X7.shape[1],"rank":rank7,"full_rank":bool(rank7==X7.shape[1]),"material_events_next":int(core.material_next.sum()),"impact_events_next":int(core.impact_next.sum()),"incident_events_next":int(core.incident_next.sum()),"clusters":int(core.LongId.nunique()),"pass":bool(rank7==X7.shape[1] and core.LongId.nunique()>=300)}
X72,n72=design_matrix(tmp,["material_t","P_t","E_t"],["wave_t"])
rank72=int(np.linalg.matrix_rank(X72))
gate7["checks"]["TQ2_rank"]={"parameters":X72.shape[1],"rank":rank72,"full_rank":bool(rank72==X72.shape[1]),"clusters":int(core.LongId.nunique()),"pass":bool(rank72==X72.shape[1] and core.LongId.nunique()>=300)}
gate7["checks"]["window_boundary"]={"public_interview_dates_available":False,"retrospective_12m_overlap_possible":True,"claim_boundary":"lagged-wave association only; no strict temporal precedence or causality","pass":True}
if not gate7["checks"]["P_variance"]["pass"] or not all(v["pass"] for v in domchecks.values()) or not gate7["checks"]["TQ1_rank"]["pass"] or not gate7["checks"]["TQ2_rank"]["pass"]:
    gate7["verdict"]="FAIL_REDESIGN"
write_json(GATES/"Q0_E7_G0_G1_G2_G3_GATE.json",gate7)

# freeze model/spec decisions
specs={
 "E3_GAM":{
   "role":"functional-form robustness only",
   "formula":"Y_material_core ~ te(E_c, P_c, k=c(4,4), bs=c('tp','tp')) + T + factor(sizeb) + factor(target_year) + factor(sector_comb2)",
   "family":"quasibinomial(logit)",
   "weights":"material_weight_equal_year",
   "method":"REML",
   "basis_rule":"single frozen tensor-product thin-plate specification; no post-outcome basis/k search",
   "inference_rule":"model-based approximate smooth uncertainty is sensitivity evidence only; if fit/uncertainty is unstable, downgrade inferential verdict to NOT_CHECKABLE and retain descriptive surface"
 },
 "E6":{
   "population":"private-sector SMEs sizeb 1-3, sectors 1-13, CSBS 2023-2025",
   "primary_outcome":"material-core consequence conditional on Q56A routing",
   "secondary_outcome":"operational-impact consequence",
   "P_items":P_ITEMS,
   "P_domains":P_DOMAINS,
   "comparator":"raw count of same 10 items",
   "controls":["target_year","sector_comb2","sizeb"],
   "weighting":"preserve official within-wave weight ratios, then rescale each included year to equal total analysis weight separately for routing, material, and impact endpoints",
   "folds":"10 deterministic 5-fold repeats stratified by year and outcome, identical P/count folds"
 },
 "E7":{
   "population":"CSLS medium businesses qsize=2 at t, adjacent waves",
   "P_domains":{"technical_protection":["rulesf","rulesg"],"access_device_control":["rulesh","rulesi"],"monitoring":["rulesb"],"backup_resilience":["rulesd","rulese"],"data_governance":["rulesc"],"formal_governance":["gov6"],"risk_management":["identb"]},
   "E_items":["onlinea","onlineb","devices"],
   "TQ1_primary":"material_next ~ P_t + E_t + material_t + factor(wave_t), pooled logistic, LongId-clustered robust SE",
   "TQ1_secondary":["impact_next","incident_next"],
   "TQ2_primary":"P_next ~ material_t + P_t + E_t + factor(wave_t), linear ANCOVA-style, LongId-clustered robust SE",
   "TQ2_secondary_predictors":["impact_t","incident_t"],
   "sensitivity":["exchangeable GEE","cross-sectional wght_t sensitivity"],
   "claim_boundary":"lagged-wave association / evidence consistent with performance feedback only"
 },
 "E8":{
   "population":"Study 8971 predictor-complete common SME population before Q56A conditioning",
   "endpoint":"attack_routed_q56a combines attack occurrence plus detection/reporting",
   "SEL0":"routing ~ factor(sizeb)+factor(target_year)+factor(sector_comb2)",
   "SEL1":"SEL0 + E_c + P_c",
   "SEL2":"SEL1 + E_c:P_c",
   "weight":"selection_weight_equal_year",
   "claim_boundary":"selection/detection relevance only; not pure attack risk/detection and cannot rescue Process-B ERCA"
 }
}
write_json(Q0/"Q0_FROZEN_MODEL_SPECS.json",specs)

# summary
summary={
 "verdict":"PASS" if gate8971["verdict"]=="PASS" and gate6["verdict"]=="PASS" and gate7["verdict"]=="PASS" else "BLOCK",
 "gates":{"8971":gate8971["verdict"],"E6":gate6["verdict"],"E7":gate7["verdict"]},
 "counts":{"8971_base":len(x),"8971_primary":len(primary),"8971_impact":len(impact),"E6_primary":len(rprimary),"E6_impact":len(rimpact),"E7_transitions":len(core),"E7_orgs":int(core.LongId.nunique())}
}
write_json(Q0/"Q0_PREFIT_SUMMARY.json",summary)
print(json.dumps(summary,indent=2))
