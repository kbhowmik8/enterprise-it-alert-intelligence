
import io, re
from collections import Counter
import numpy as np
import pandas as pd
 
CANONICAL = {
 "alert_id":["alert_id","number","alert number","incident","ticket"],
 "severity":["severity","priority"],
 "criticality":["criticality","business criticality","impact"],
 "assignment_group":["assignment_group","assignment group","support group"],
 "configuration_item":["configuration_item","configuration item","ci","cmdb_ci"],
 "created_at":["created_at","created","opened_at","opened"],
 "updated_at":["updated_at","updated","sys_updated_on","last updated"],
 "reopened":["reopened","reopen status","reopened status","reopen_count"],
 "description":["description","short_description","short description"],
 "work_notes":["work_notes","work notes","comments"]}
STOP={"the","a","an","and","or","to","of","for","in","on","is","are","was","with","from","at","by","this","that","alert","issue"}
 
def read_excel(upload):
    return pd.read_excel(upload, engine="openpyxl")
 
def normalize(df):
    d=df.copy(); lookup={str(c).strip().lower().replace("_"," "):c for c in d.columns}; ren={}
    for canonical, aliases in CANONICAL.items():
        for a in aliases:
            key=a.lower().replace("_"," ")
            if key in lookup: ren[lookup[key]]=canonical; break
    d=d.rename(columns=ren)
    missing=[c for c in CANONICAL if c not in d.columns]
    if missing: raise ValueError("Missing required columns: "+", ".join(missing))
    for c in ["severity","criticality","assignment_group","configuration_item","description","work_notes"]:
        d[c]=d[c].fillna("Unknown").astype(str).str.strip()
    for c in ["created_at","updated_at"]: d[c]=pd.to_datetime(d[c], errors="coerce")
    d["reopened_bool"]=d["reopened"].astype(str).str.lower().isin(["yes","true","1","reopened","y"]) | (pd.to_numeric(d["reopened"],errors="coerce").fillna(0)>0)
    d["update_hours"]=(d["updated_at"]-d["created_at"]).dt.total_seconds().div(3600).clip(lower=0)
    d["created_day"]=d["created_at"].dt.day_name().fillna("Unknown")
    d["created_hour"]=d["created_at"].dt.hour.fillna(-1).astype(int)
    d["signature"]=(d["severity"].str.lower()+"|"+d["assignment_group"].str.lower()+"|"+d["configuration_item"].str.lower()+"|"+d["description"].map(signature_text))
    return d
 
def signature_text(x):
    words=[w for w in re.findall(r"[a-z0-9]+",str(x).lower()) if w not in STOP and len(w)>2]
    return " ".join(words[:5]) or "unknown"
 
def summary(prev, cur):
    total_prev,total_cur=len(prev),len(cur)
    delta=total_cur-total_prev; pct=(delta/total_prev*100) if total_prev else None
    return {"total_prev":total_prev,"total_cur":total_cur,"delta":delta,"pct":pct,
      "reopen_prev":float(prev.reopened_bool.mean()*100) if total_prev else 0,
      "reopen_cur":float(cur.reopened_bool.mean()*100) if total_cur else 0,
      "median_update_prev":float(prev.update_hours.median()) if total_prev else 0,
      "median_update_cur":float(cur.update_hours.median()) if total_cur else 0}
 
def comparative(prev,cur,column):
    a=prev[column].value_counts().rename("previous"); b=cur[column].value_counts().rename("current")
    out=pd.concat([a,b],axis=1).fillna(0).astype(int).reset_index().rename(columns={"index":column})
    out["delta"]=out.current-out.previous
    out["change_pct"]=np.where(out.previous>0,out.delta/out.previous*100,np.nan)
    return out.sort_values(["current","delta"],ascending=False)
 
def common_factors(prev,cur):
    rows=[]
    for col in ["severity","criticality","assignment_group","configuration_item","created_day","created_hour","reopened_bool"]:
        x=comparative(prev,cur,col).head(10).copy(); x.insert(0,"factor",col); x=x.rename(columns={col:"value"}); rows.append(x)
    out=pd.concat(rows,ignore_index=True)
    # Stacking str, int and bool factors leaves 'value' as object, which Arrow cannot serialize.
    out["value"]=out["value"].astype(str)
    return out
 
def keywords(df,n=20):
    text=" ".join((df.description+" "+df.work_notes).astype(str)).lower()
    words=[w for w in re.findall(r"[a-z0-9]+",text) if w not in STOP and len(w)>2]
    return pd.DataFrame(Counter(words).most_common(n),columns=["keyword","count"])
 
def forecast(prev,cur):
    p=prev.signature.value_counts(); c=cur.signature.value_counts(); keys=sorted(set(p.index)|set(c.index)); rows=[]
    for k in keys:
        pv=int(p.get(k,0)); cv=int(c.get(k,0)); recurring=(pv>0 and cv>0)
        group=cur[cur.signature==k] if cv else prev[prev.signature==k]
        sev=group.severity.mode().iloc[0] if len(group) else "Unknown"
        crit=group.criticality.mode().iloc[0] if len(group) else "Unknown"
        ag=group.assignment_group.mode().iloc[0] if len(group) else "Unknown"
        ci=group.configuration_item.mode().iloc[0] if len(group) else "Unknown"
        desc=group.description.mode().iloc[0] if len(group) else "Unknown"
        reopen=float(group.reopened_bool.mean()) if len(group) else 0
        # Transparent empirical-Bayes recurrence score, not a calibrated ML probability.
        base=(cv+1)/(cv+3); persistence=0.18 if recurring else 0; trend=0.08 if cv>pv else (-0.04 if cv<pv else 0); risk=0.06*reopen
        prob=max(0.05,min(0.95,base+persistence+trend+risk))
        rows.append([k,pv,cv,round(prob*100,1),sev,crit,ag,ci,desc,recurring])
    out=pd.DataFrame(rows,columns=["signature","previous_count","current_count","probability_pct","severity","criticality","assignment_group","configuration_item","description","repeated_both_weeks"])
    if out.empty: return out
    return out.sort_values(["probability_pct","current_count"],ascending=False).reset_index(drop=True)
 
def build_excel(prev,cur):
    output=io.BytesIO()
    with pd.ExcelWriter(output,engine="openpyxl") as w:
        pd.DataFrame([summary(prev,cur)]).to_excel(w,sheet_name="Executive Summary",index=False)
        for col,name in [("severity","Severity"),("criticality","Criticality"),("assignment_group","Assignment Groups"),("configuration_item","Configuration Items"),("created_day","Creation Day")]: comparative(prev,cur,col).to_excel(w,sheet_name=name[:31],index=False)
        common_factors(prev,cur).to_excel(w,sheet_name="Common Factors",index=False); forecast(prev,cur).to_excel(w,sheet_name="Forecast",index=False)
        prev.to_excel(w,sheet_name="Previous Normalized",index=False); cur.to_excel(w,sheet_name="Current Normalized",index=False)
    output.seek(0); return output.getvalue()
 
def build_pdf(prev,cur):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
    out=io.BytesIO(); doc=SimpleDocTemplate(out,pagesize=landscape(A4),rightMargin=24,leftMargin=24,topMargin=24,bottomMargin=24); styles=getSampleStyleSheet(); story=[]; s=summary(prev,cur)
    story += [Paragraph("Alert Intelligence Comparative Report",styles["Title"]),Paragraph("Previous week versus current week",styles["Normal"]),Spacer(1,12)]
    story.append(Table([["Metric","Previous","Current","Change"],["Alert volume",s["total_prev"],s["total_cur"],s["delta"]],["Reopen rate",f'{s["reopen_prev"]:.1f}%',f'{s["reopen_cur"]:.1f}%',f'{s["reopen_cur"]-s["reopen_prev"]:+.1f} pp'],["Median update hours",f'{s["median_update_prev"]:.1f}',f'{s["median_update_cur"]:.1f}',f'{s["median_update_cur"]-s["median_update_prev"]:+.1f}']]))
    story += [Spacer(1,14),Paragraph("Highest-probability repeat alerts",styles["Heading2"])]
    f=forecast(prev,cur).head(15); data=[["Probability","Current","Previous","Severity","Group","Configuration item","Description"]]+[[f'{r.probability_pct:.1f}%',r.current_count,r.previous_count,str(r.severity),str(r.assignment_group)[:24],str(r.configuration_item)[:24],str(r.description)[:50]] for _,r in f.iterrows()]
    t=Table(data,repeatRows=1,colWidths=[60,45,45,55,115,115,260]); t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#123B5D")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.25,colors.grey),("FONTSIZE",(0,0),(-1,-1),7),("VALIGN",(0,0),(-1,-1),"TOP")])) ; story.append(t)
    story += [Spacer(1,12),Paragraph("Forecast note: probabilities are transparent recurrence scores estimated from only two weekly snapshots. Validate against a longer history before operational automation.",styles["Italic"])]
    doc.build(story); out.seek(0); return out.getvalue()
 