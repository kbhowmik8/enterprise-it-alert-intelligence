
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
 
def data_quality(prev,cur):
    return pd.DataFrame({"week":["Previous","Current"],"rows":[len(prev),len(cur)],
        "missing_created":[int(prev.created_at.isna().sum()),int(cur.created_at.isna().sum())],
        "missing_updated":[int(prev.updated_at.isna().sum()),int(cur.updated_at.isna().sum())],
        "duplicate_alert_ids":[int(prev.alert_id.duplicated().sum()),int(cur.alert_id.duplicated().sum())]})

# (column, sheet/section name, chart title, render horizontally) - mirrors the dashboard tabs.
BREAKDOWNS=[("severity","Severity","Alerts by severity",False),
            ("criticality","Criticality","Alerts by criticality",False),
            ("assignment_group","Assignment Groups","Top assignment groups",True),
            ("configuration_item","Configuration Items","Top configuration items",True),
            ("created_day","Creation Day","Alerts by creation day",False),
            ("created_hour","Creation Hour","Alerts by creation hour",False),
            ("reopened_bool","Reopened","Alerts by reopen status",False)]

def _summary_rows(s):
    pct="N/A" if s["pct"] is None else f'{s["pct"]:+.1f}%'
    return [["Metric","Previous","Current","Change"],
            ["Alert volume",s["total_prev"],s["total_cur"],f'{s["delta"]:+d}'],
            ["Week-over-week","","",pct],
            ["Reopen rate",f'{s["reopen_prev"]:.1f}%',f'{s["reopen_cur"]:.1f}%',f'{s["reopen_cur"]-s["reopen_prev"]:+.1f} pp'],
            ["Median update hours",f'{s["median_update_prev"]:.1f}',f'{s["median_update_cur"]:.1f}',f'{s["median_update_cur"]-s["median_update_prev"]:+.1f}']]

def build_excel(prev,cur):
    from openpyxl.chart import BarChart, Reference
    output=io.BytesIO()
    with pd.ExcelWriter(output,engine="openpyxl") as w:
        s=summary(prev,cur); rows=_summary_rows(s)
        pd.DataFrame(rows[1:],columns=rows[0]).to_excel(w,sheet_name="Executive Summary",index=False)
        for col,name,title,horizontal in BREAKDOWNS:
            table=comparative(prev,cur,col)
            if horizontal: table=table.head(15)
            sheet=name[:31]; table.to_excel(w,sheet_name=sheet,index=False)
            if len(table):
                ws=w.sheets[sheet]
                chart=BarChart(); chart.type="bar" if horizontal else "col"
                chart.title=title; chart.width=24; chart.height=12; chart.y_axis.title="Alerts"
                chart.add_data(Reference(ws,min_col=2,max_col=3,min_row=1,max_row=len(table)+1),titles_from_data=True)
                chart.set_categories(Reference(ws,min_col=1,min_row=2,max_row=len(table)+1))
                ws.add_chart(chart,"H2")
        common_factors(prev,cur).to_excel(w,sheet_name="Common Factors",index=False)
        forecast(prev,cur).to_excel(w,sheet_name="Forecast",index=False)
        keywords(cur).to_excel(w,sheet_name="Keywords Current",index=False)
        keywords(prev).to_excel(w,sheet_name="Keywords Previous",index=False)
        data_quality(prev,cur).to_excel(w,sheet_name="Data Quality",index=False)
        prev.to_excel(w,sheet_name="Previous Normalized",index=False)
        cur.to_excel(w,sheet_name="Current Normalized",index=False)
    output.seek(0); return output.getvalue()

def _pdf_chart(table,column,title,width,height,horizontal=False):
    from reportlab.lib import colors
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.graphics.charts.barcharts import VerticalBarChart, HorizontalBarChart
    from reportlab.graphics.charts.legends import Legend
    prev_c, cur_c = colors.HexColor("#a9c1d4"), colors.HexColor("#1e6091")
    cats=[str(v)[:26] for v in table[column].tolist()]
    d=Drawing(width,height)
    d.add(String(4,height-14,title,fontSize=11,fontName="Helvetica-Bold",fillColor=colors.HexColor("#123B5D")))
    bc=HorizontalBarChart() if horizontal else VerticalBarChart()
    bc.x=150 if horizontal else 42; bc.y=34
    bc.width=width-bc.x-24; bc.height=height-64
    bc.data=[table["previous"].tolist(),table["current"].tolist()]
    bc.categoryAxis.categoryNames=cats
    bc.categoryAxis.labels.fontSize=7
    bc.valueAxis.valueMin=0
    bc.valueAxis.labels.fontSize=7
    bc.barSpacing=1; bc.groupSpacing=6
    bc.bars[0].fillColor=prev_c; bc.bars[1].fillColor=cur_c
    bc.bars.strokeWidth=0.25
    if not horizontal:
        bc.categoryAxis.labels.angle=25; bc.categoryAxis.labels.boxAnchor="ne"; bc.categoryAxis.labels.dy=-4
    d.add(bc)
    lg=Legend(); lg.x=width-118; lg.y=height-10; lg.boxAnchor="nw"; lg.fontSize=7
    lg.colorNamePairs=[(prev_c,"previous"),(cur_c,"current")]
    lg.columnMaximum=1; lg.deltax=62; lg.dxTextSpace=4; lg.dx=6; lg.dy=6
    d.add(lg)
    return d

def _pdf_table(data,col_widths,font_size=7):
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle
    t=Table(data,repeatRows=1,colWidths=col_widths)
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#123B5D")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("GRID",(0,0),(-1,-1),0.25,colors.HexColor("#b9c7d6")),("FONTSIZE",(0,0),(-1,-1),font_size),
        ("VALIGN",(0,0),(-1,-1),"TOP"),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f2f6fa")])]))
    return t

def build_pdf(prev,cur):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak
    out=io.BytesIO()
    doc=SimpleDocTemplate(out,pagesize=landscape(A4),rightMargin=24,leftMargin=24,topMargin=24,
                          bottomMargin=24,title="Alert Intelligence Comparative Report")
    styles=getSampleStyleSheet(); w=doc.width; story=[]; s=summary(prev,cur)

    story+=[Paragraph("Alert Intelligence Comparative Report",styles["Title"]),
            Paragraph("Previous week versus current week",styles["Normal"]),Spacer(1,14),
            Paragraph("Executive summary",styles["Heading2"]),Spacer(1,6),
            _pdf_table(_summary_rows(s),[170,90,90,110],8),Spacer(1,16)]
    tables={col:comparative(prev,cur,col) for col,_,_,_ in BREAKDOWNS}
    story+=[_pdf_chart(tables["severity"],"severity","Alerts by severity",w,205),Spacer(1,10),
            _pdf_chart(tables["criticality"],"criticality","Alerts by criticality",w,205),PageBreak()]

    story+=[Paragraph("Where the alerts come from",styles["Heading2"]),Spacer(1,6),
            _pdf_chart(tables["assignment_group"].head(12),"assignment_group","Top assignment groups",w,235,True),
            Spacer(1,12),
            _pdf_chart(tables["configuration_item"].head(12),"configuration_item","Top configuration items",w,235,True),
            PageBreak()]

    story+=[Paragraph("When the alerts arrive",styles["Heading2"]),Spacer(1,6),
            _pdf_chart(tables["created_day"],"created_day","Alerts by creation day",w,220),Spacer(1,12),
            _pdf_chart(tables["created_hour"].sort_values("created_hour"),"created_hour","Alerts by creation hour",w,220),
            PageBreak()]

    f=forecast(prev,cur)
    head=[["Probability","Current","Previous","Severity","Group","Configuration item","Description"]]
    body=[[f'{r.probability_pct:.1f}%',r.current_count,r.previous_count,str(r.severity)[:16],
           str(r.assignment_group)[:26],str(r.configuration_item)[:24],str(r.description)[:62]]
          for _,r in f.head(22).iterrows()]
    story+=[Paragraph("Highest-probability repeat alerts",styles["Heading2"]),Spacer(1,6),
            _pdf_table(head+body,[58,44,46,72,132,120,222]),Spacer(1,10),
            Paragraph("Forecast note: probabilities are transparent recurrence scores estimated from only "
                      "two weekly snapshots. Validate against a longer history before operational automation.",
                      styles["Italic"]),PageBreak()]

    cf=common_factors(prev,cur)
    cf_rows=[["Factor","Value","Previous","Current","Delta"]]+[
        [str(r.factor),str(r.value)[:40],r.previous,r.current,f'{r.delta:+d}'] for _,r in cf.iterrows()]
    story+=[Paragraph("Most common categorical factors",styles["Heading2"]),Spacer(1,6),
            _pdf_table(cf_rows,[130,240,90,90,90],6.5),PageBreak()]

    kc,kp=keywords(cur),keywords(prev)
    kw_rows=[["Current keyword","Count","Previous keyword","Count"]]+[
        [kc.keyword.iloc[i] if i<len(kc) else "", kc["count"].iloc[i] if i<len(kc) else "",
         kp.keyword.iloc[i] if i<len(kp) else "", kp["count"].iloc[i] if i<len(kp) else ""]
        for i in range(max(len(kc),len(kp)))]
    dq=data_quality(prev,cur)
    dq_rows=[list(dq.columns)]+dq.astype(str).values.tolist()
    story+=[Paragraph("Description and work-note keywords",styles["Heading2"]),Spacer(1,6),
            _pdf_table(kw_rows,[220,90,220,90]),Spacer(1,18),
            Paragraph("Data quality",styles["Heading2"]),Spacer(1,6),
            _pdf_table(dq_rows,[110,90,150,150,160],8)]

    doc.build(story); out.seek(0); return out.getvalue()
 