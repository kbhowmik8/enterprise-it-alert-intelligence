
import io

import streamlit as st
import pandas as pd
import plotly.express as px
from analysis_engine import read_excel,normalize,summary,comparative,common_factors,keywords,forecast,data_quality,build_excel,build_pdf

st.set_page_config(page_title="Alert Intelligence", page_icon="📡", layout="wide",
                   initial_sidebar_state="collapsed")

INK, MUTED, BRAND = "#0f2b46", "#5b7189", "#1e6091"
PALETTE = ["#1e6091", "#2a9d8f", "#e9c46a", "#f4a261", "#e76f51", "#8e7dbe"]
WEEK_COLORS = {"previous": "#a9c1d4", "current": "#1e6091"}

st.markdown(f"""<style>
.block-container{{padding-top:2rem;padding-bottom:3rem;max-width:1500px}}
#MainMenu,footer{{visibility:hidden}}
.hero{{background:linear-gradient(120deg,#0f2b46 0%,#1e6091 58%,#2a9d8f 100%);border-radius:18px;
 padding:30px 36px;margin-bottom:26px;box-shadow:0 10px 30px rgba(15,43,70,.18)}}
.hero .h{{margin:0 0 8px;font-size:2.05rem;font-weight:700;letter-spacing:-.5px;color:#fff}}
.hero p{{margin:0;font-size:1.02rem;line-height:1.55;color:rgba(255,255,255,.86);max-width:72ch}}
.chips{{margin-top:18px;display:flex;gap:8px;flex-wrap:wrap}}
.chips span{{background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.28);
 padding:5px 13px;border-radius:999px;font-size:.78rem;color:#fff}}
.bar{{display:flex;align-items:center;gap:14px;background:#fff;border:1px solid #e4ebf3;
 border-radius:14px;padding:14px 20px;margin-bottom:22px;box-shadow:0 1px 3px rgba(15,43,70,.06)}}
.bar .t{{font-weight:700;color:{INK};font-size:1.15rem}}
.bar .s{{color:{MUTED};font-size:.87rem}}
[data-testid="stVerticalBlockBorderWrapper"]{{background:#fff;border-radius:14px;
 border:1px solid #e4ebf3;box-shadow:0 1px 3px rgba(15,43,70,.06)}}
[data-testid="stMetric"]{{background:#fff;border:1px solid #e4ebf3;border-radius:14px;
 padding:16px 18px;box-shadow:0 1px 3px rgba(15,43,70,.06)}}
[data-testid="stMetricLabel"] p{{color:{MUTED};font-weight:600;font-size:.82rem}}
[data-testid="stTabs"] button[role="tab"]{{font-weight:600;color:{MUTED}}}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"]{{color:{BRAND}}}
.step{{font-size:.72rem;font-weight:700;letter-spacing:.11em;text-transform:uppercase;color:{BRAND}}}
.ctitle{{font-size:1.06rem;font-weight:700;color:{INK};margin:3px 0 3px}}
.csub{{font-size:.86rem;color:{MUTED};margin-bottom:12px;line-height:1.45}}
.feat .ft{{margin:0 0 5px;font-size:.97rem;font-weight:700;color:{INK}}}
.feat p{{margin:0;font-size:.85rem;color:{MUTED};line-height:1.5}}
.sec{{font-size:1.12rem;font-weight:700;color:{INK};margin:6px 0 12px}}
</style>""", unsafe_allow_html=True)

st.session_state.setdefault("view", "home")
st.session_state.setdefault("dataset", None)


# Caches are bounded: entries hold whole parsed workbooks plus generated Excel/PDF, and the
# ttl also stops uploaded alert data lingering in server memory after a session ends.
@st.cache_data(show_spinner=False, ttl=3600, max_entries=6)
def load_weeks(prev_bytes, cur_bytes):
    return normalize(read_excel(io.BytesIO(prev_bytes))), normalize(read_excel(io.BytesIO(cur_bytes)))


@st.cache_data(show_spinner=False, ttl=3600, max_entries=3)
def build_reports(prev_bytes, cur_bytes):
    prev, cur = load_weeks(prev_bytes, cur_bytes)
    return build_excel(prev, cur), build_pdf(prev, cur)


def styled(fig, height=380, legend_title=None):
    fig.update_layout(template="plotly_white", height=height, margin=dict(l=8, r=8, t=52, b=8),
                      title_font=dict(size=15, color=INK), font=dict(color="#3d566e"),
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1,
                                  title_text=legend_title or ""),
                      plot_bgcolor="rgba(0,0,0,0)")
    return fig


def goto(view):
    st.session_state.view = view
    st.rerun()


def render_home():
    st.markdown("""<div class="hero">
      <div class="h">📡 Weekly Alert Intelligence</div>
      <p>Compare last week's and this week's alert exports to see what changed, which groups and
      configuration items are driving the noise, and which alert patterns are most likely to return.</p>
      <div class="chips"><span>Privacy-first</span><span>No external AI calls</span>
      <span>Excel &amp; PDF export</span><span>Processed in memory</span></div>
    </div>""", unsafe_allow_html=True)

    if st.session_state.dataset:
        d = st.session_state.dataset
        a, b = st.columns([3, 1])
        a.info(f"Analysis ready for **{d['prev_name']}** → **{d['cur_name']}**.")
        if b.button("Back to analysis  →", width="stretch"):
            goto("analysis")

    st.markdown('<div class="sec">Upload the two weekly exports</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="large")
    with c1, st.container(border=True):
        st.markdown('<div class="step">Step 1</div><div class="ctitle">Previous week</div>'
                    '<div class="csub">The baseline export you want to compare against.</div>',
                    unsafe_allow_html=True)
        prev_file = st.file_uploader("Previous week", type=["xlsx"], key="up_prev",
                                     label_visibility="collapsed")
        if prev_file:
            st.success(prev_file.name, icon="✅")
    with c2, st.container(border=True):
        st.markdown('<div class="step">Step 2</div><div class="ctitle">Current week</div>'
                    '<div class="csub">The newer export to measure the change against.</div>',
                    unsafe_allow_html=True)
        cur_file = st.file_uploader("Current week", type=["xlsx"], key="up_cur",
                                    label_visibility="collapsed")
        if cur_file:
            st.success(cur_file.name, icon="✅")

    ready = prev_file is not None and cur_file is not None
    run, note = st.columns([1, 3])
    clicked = run.button("Run analysis  →", type="primary", width="stretch", disabled=not ready)
    if not ready:
        note.caption("Upload both workbooks to enable the analysis.")
    if clicked:
        pb, cb = prev_file.getvalue(), cur_file.getvalue()
        try:
            load_weeks(pb, cb)
        except Exception as e:
            st.error(f"Could not read these workbooks: {e}")
        else:
            st.session_state.dataset = {"prev_bytes": pb, "cur_bytes": cb,
                                        "prev_name": prev_file.name, "cur_name": cur_file.name}
            goto("analysis")

    st.markdown('<div class="sec">What you get</div>', unsafe_allow_html=True)
    for col, (title, body) in zip(st.columns(4, gap="medium"), [
        ("📊 Executive view", "Volume, severity, criticality and reopen-rate movement at a glance."),
        ("🔍 Comparative drill-down", "Break the week down by group, configuration item, day and hour."),
        ("🔮 Recurrence risk", "Alert signatures ranked by how likely they are to come back."),
        ("📤 Shareable reports", "One-click Excel workbook and formatted PDF summary."),
    ]):
        with col, st.container(border=True):
            st.markdown(f'<div class="feat"><div class="ft">{title}</div><p>{body}</p></div>',
                        unsafe_allow_html=True)

    with st.expander("Which columns does each workbook need?"):
        st.markdown(
            "Each workbook needs one row per alert, with these columns: "
            "`alert_id`, `severity`, `criticality`, `assignment_group`, `configuration_item`, "
            "`created_at`, `updated_at`, `reopened`, `description`, `work_notes`.\n\n"
            "Common ServiceNow-style aliases are mapped automatically, so headers such as "
            "`number`, `priority`, `impact`, `cmdb_ci`, `opened_at`, `sys_updated_on` or "
            "`short_description` are also accepted."
        )


def render_analysis():
    d = st.session_state.dataset
    try:
        prev, cur = load_weeks(d["prev_bytes"], d["cur_bytes"])
    except Exception as e:
        st.error(f"Could not read these workbooks: {e}")
        if st.button("← Back to home"):
            goto("home")
        return

    nav, title = st.columns([1, 6])
    with nav:
        if st.button("←  Home", width="stretch"):
            goto("home")
    with title:
        st.markdown(f'<div class="bar"><div><div class="t">📡 Weekly Alert Intelligence</div>'
                    f'<div class="s">Comparing <b>{d["prev_name"]}</b> → <b>{d["cur_name"]}</b></div>'
                    f'</div></div>', unsafe_allow_html=True)

    s = summary(prev, cur)
    a, b, c, e = st.columns(4)
    a.metric("Current alerts", s["total_cur"], s["delta"])
    b.metric("Week-over-week", f'{s["pct"]:.1f}%' if s["pct"] is not None else "N/A")
    c.metric("Current reopen rate", f'{s["reopen_cur"]:.1f}%', f'{s["reopen_cur"]-s["reopen_prev"]:+.1f} pp',
             delta_color="inverse")
    e.metric("Median update time", f'{s["median_update_cur"]:.1f} h',
             f'{s["median_update_cur"]-s["median_update_prev"]:+.1f} h', delta_color="inverse")

    tabs = st.tabs(["Executive dashboard", "Comparative analysis", "Forecast",
                    "Common factors", "Data quality & export"])

    with tabs[0]:
        col1, col2 = st.columns(2, gap="medium")
        with col1, st.container(border=True):
            x = comparative(prev, cur, "severity").melt("severity", value_vars=["previous", "current"],
                                                        var_name="week", value_name="alerts")
            st.plotly_chart(styled(px.bar(x, x="severity", y="alerts", color="week", barmode="group",
                                          title="Alerts by severity", color_discrete_map=WEEK_COLORS)),
                            width="stretch")
        with col2, st.container(border=True):
            x = comparative(prev, cur, "criticality").melt("criticality", value_vars=["previous", "current"],
                                                           var_name="week", value_name="alerts")
            st.plotly_chart(styled(px.bar(x, x="criticality", y="alerts", color="week", barmode="group",
                                          title="Alerts by criticality", color_discrete_map=WEEK_COLORS)),
                            width="stretch")
        with st.container(border=True):
            x = comparative(prev, cur, "assignment_group").head(12).melt(
                "assignment_group", value_vars=["previous", "current"], var_name="week", value_name="alerts")
            st.plotly_chart(styled(px.bar(x, x="alerts", y="assignment_group", color="week", barmode="group",
                                          orientation="h", title="Top assignment groups",
                                          color_discrete_map=WEEK_COLORS), height=460), width="stretch")

    with tabs[1]:
        with st.container(border=True):
            dimension = st.selectbox("Break the week down by", ["severity", "criticality", "assignment_group",
                                                                "configuration_item", "created_day",
                                                                "created_hour", "reopened_bool"])
            st.dataframe(comparative(prev, cur, dimension), width="stretch", hide_index=True)
        with st.container(border=True):
            st.markdown('<div class="sec">Update-time distribution</div>', unsafe_allow_html=True)
            times = pd.concat([prev.assign(week="Previous"), cur.assign(week="Current")])
            st.plotly_chart(styled(px.box(times, x="week", y="update_hours", color="week", points="outliers",
                                          color_discrete_sequence=PALETTE)), width="stretch")

    with tabs[2]:
        st.warning("This is a recurrence-risk score from two snapshots, not a statistically calibrated "
                   "prediction. Use 8–12+ weeks for production forecasting.", icon="⚠️")
        f = forecast(prev, cur)
        with st.container(border=True):
            threshold = st.slider("Minimum repeat probability", 5, 95, 50, 5)
            view = f[f.probability_pct >= threshold]
            st.caption(f"{len(view)} of {len(f)} alert signatures at or above {threshold}%.")
            st.dataframe(view[["probability_pct", "previous_count", "current_count", "severity", "criticality",
                               "assignment_group", "configuration_item", "description", "repeated_both_weeks"]],
                         width="stretch", hide_index=True)
        if len(view):
            with st.container(border=True):
                st.plotly_chart(styled(px.bar(view.head(20), x="probability_pct", y="configuration_item",
                                              color="severity", orientation="h",
                                              title="Highest-probability repeat alerts",
                                              color_discrete_sequence=PALETTE), height=460), width="stretch")

    with tabs[3]:
        with st.container(border=True):
            st.markdown('<div class="sec">Most common categorical factors</div>', unsafe_allow_html=True)
            st.dataframe(common_factors(prev, cur), width="stretch", hide_index=True)
        x, y = st.columns(2, gap="medium")
        with x, st.container(border=True):
            st.markdown('<div class="sec">Current week keywords</div>', unsafe_allow_html=True)
            st.dataframe(keywords(cur), hide_index=True, width="stretch")
        with y, st.container(border=True):
            st.markdown('<div class="sec">Previous week keywords</div>', unsafe_allow_html=True)
            st.dataframe(keywords(prev), hide_index=True, width="stretch")

    with tabs[4]:
        with st.container(border=True):
            st.markdown('<div class="sec">Data quality</div>', unsafe_allow_html=True)
            st.dataframe(data_quality(prev, cur), width="stretch", hide_index=True)
        with st.container(border=True):
            st.markdown('<div class="sec">Export report</div>', unsafe_allow_html=True)
            xlsx, pdf = build_reports(d["prev_bytes"], d["cur_bytes"])
            x, y = st.columns(2)
            x.download_button("⬇  Download Excel report", xlsx, "alert_comparative_report.xlsx",
                              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                              width="stretch")
            y.download_button("⬇  Download PDF report", pdf, "alert_comparative_report.pdf",
                              "application/pdf", width="stretch")


if st.session_state.view == "analysis" and st.session_state.dataset:
    render_analysis()
else:
    render_home()
 