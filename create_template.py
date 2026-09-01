import pandas as pd
cols=["alert_id","severity","criticality","assignment_group","configuration_item","created_at","updated_at","reopened","description","work_notes"]
pd.DataFrame(columns=cols).to_excel("alert_import_template.xlsx",index=False,engine="openpyxl")
print("Created alert_import_template.xlsx")
 