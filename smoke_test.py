from analysis_engine import (read_excel, normalize, summary, comparative,
                            common_factors, keywords, forecast, build_excel, build_pdf)

prev = normalize(read_excel("alerts_previous_week.xlsx"))
cur = normalize(read_excel("alerts_current_week.xlsx"))
print("normalize OK", prev.shape, cur.shape)

s = summary(prev, cur)
print("summary OK", {k: (round(v, 2) if isinstance(v, float) else v) for k, v in s.items()})

for col in ["severity", "criticality", "assignment_group", "configuration_item",
            "created_day", "created_hour", "reopened_bool"]:
    c = comparative(prev, cur, col)
    assert not c.empty, col
print("comparative OK")

print("common_factors OK", common_factors(prev, cur).shape)
print("keywords OK", keywords(cur).head(3).to_dict("records"))

f = forecast(prev, cur)
print("forecast OK", f.shape)
print(f.head(3)[["probability_pct", "previous_count", "current_count", "severity"]].to_string())

x = build_excel(prev, cur)
print("build_excel OK", len(x), "bytes")
p = build_pdf(prev, cur)
print("build_pdf OK", len(p), "bytes")
