 
from fastapi import FastAPI,UploadFile,File,HTTPException
from analysis_engine import read_excel,normalize,summary,forecast,common_factors
app=FastAPI(title="Alert Intelligence API",version="1.0.0",description="Comparative weekly alert analysis for Copilot Studio")
@app.get("/health",operation_id="health")
def health(): return {"status":"ok"}
@app.post("/analyze",operation_id="analyzeWeeklyAlerts")
async def analyze(previous_week:UploadFile=File(...),current_week:UploadFile=File(...)):
 try:
  p=normalize(read_excel(previous_week.file)); c=normalize(read_excel(current_week.file)); f=forecast(p,c).head(25); common=common_factors(p,c).head(30)
  return {"summary":summary(p,c),"forecast":f.to_dict("records"),"common_factors":common.to_dict("records")}
 except Exception as e: raise HTTPException(400,str(e))
 