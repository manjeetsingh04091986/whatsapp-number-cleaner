import streamlit as st
import pandas as pd
import io
import re
import os
import tempfile
from datetime import datetime
from atlassian import Jira

# ── Import the battle-tested cleaner (local copy, self-contained for deploy) ──
from cleaner import clean_dataframe

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Whatsapp Number Cleaning & Delivery Automation",
    page_icon="📱",
    layout="centered"
)

# ── Secrets ────────────────────────────────────────────────────────────────────
JIRA_URL       = st.secrets["JIRA_URL"]
JIRA_USER      = st.secrets["JIRA_USER"]
JIRA_API_TOKEN = st.secrets["JIRA_API_TOKEN"]
FILES_COM_KEY  = st.secrets["FILES_COM_API_KEY"]
FILES_FOLDER   = "/JLT Office/Karix - Whatsapp Data Management"


# ── Pipeline ───────────────────────────────────────────────────────────────────
def run_pipeline(df, ticket_id, upload, post_jira):

    cleaned_df, rejected_df, stats = clean_dataframe(df)

    timestamp   = datetime.now().strftime("%Y%m%d_%H%M")
    label       = f"{ticket_id}_{timestamp}" if ticket_id else timestamp
    clean_name  = f"cleaned_{label}.xlsx"
    reject_name = f"rejected_{label}.xlsx"

    clean_buf  = io.BytesIO()
    reject_buf = io.BytesIO()

    with pd.ExcelWriter(clean_buf, engine="openpyxl") as w:
        cleaned_df.to_excel(w, index=False)
    with pd.ExcelWriter(reject_buf, engine="openpyxl") as w:
        rejected_df.to_excel(w, index=False)

    clean_buf.seek(0)
    reject_buf.seek(0)

    summary = {
        "input_rows":    stats["input_rows"],
        "cleaned_rows":  stats["cleaned_rows"],
        "rejected_rows": stats["rejected_rows"],
        "duplicates":    stats["duplicates_removed"],
        "clean_name":    clean_name,
        "reject_name":   reject_name,
        "clean_buf":     clean_buf,
        "reject_buf":    reject_buf,
        "files_path":    None,
        "jira_url":      None,
    }

    # ── Upload to Files.com ────────────────────────────────────────────────────
    if upload:
        try:
            import files_sdk
            from files_sdk import file as files_com_file
            files_sdk.set_api_key(FILES_COM_KEY)
            dest_path = f"{FILES_FOLDER}/{clean_name}"

            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                tmp.write(clean_buf.getvalue())
                tmp_path = tmp.name

            files_com_file.upload_file(tmp_path, destination=dest_path)
            os.unlink(tmp_path)
            summary["files_path"] = dest_path
        except Exception as e:
            st.warning(f"⚠️ Files.com upload failed: {e}")

    # ── Post Jira comment ──────────────────────────────────────────────────────
    if post_jira:
        try:
            jira = Jira(url=JIRA_URL, username=JIRA_USER, password=JIRA_API_TOKEN)

            rej_lines = "\n".join(
                f"  - {reason}: {count}"
                for reason, count in stats.get("rejection_breakdown", {}).items()
            ) or "  - None"

            files_note = (
                f"*File uploaded to Files.com:*\n`{summary['files_path']}`\n"
                f"[Pick up from Files.com|https://dmgevents.files.com]"
                if summary["files_path"]
                else "_Files.com upload skipped or failed._"
            )

            comment = f"""
✅ *Whatsapp Number Cleaning & Delivery Automation · Run Complete*
----
|| Metric || Count ||
| Input rows | {summary['input_rows']} |
| Cleaned (valid) | {summary['cleaned_rows']} |
| Rejected | {summary['rejected_rows']} |
| Duplicates removed | {summary['duplicates']} |

*Rejection breakdown:*
{rej_lines}

{files_note}

_Run timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}_
""".strip()

            jira.issue_add_comment(ticket_id, comment)
            summary["jira_url"] = f"{JIRA_URL}/browse/{ticket_id}"
        except Exception as e:
            st.warning(f"⚠️ Jira comment failed: {e}")

    return cleaned_df, rejected_df, summary


# ── UI ─────────────────────────────────────────────────────────────────────────
st.title("📱 Whatsapp Number Cleaning & Delivery Automation")
st.caption("Upload a contact file → clean numbers → upload to Files.com → update Jira.")

st.divider()

uploaded_file = st.file_uploader(
    "Drop your CSV or Excel file here",
    type=["csv", "xlsx", "xls"],
)

st.info(
    "📋 **Column naming:** your file can have 1–6 columns, but the phone-number "
    "column **must be named `Mobile`** (spelling matters; capitalisation does not — "
    "`Mobile`, `mobile`, `MOBILE` all work). An optional column named `Country` "
    "(e.g. UAE, India) improves accuracy. All other columns (FirstName, LastName, "
    "JobTitle, ContactID, …) are kept exactly as-is in the output."
)

ticket_id = st.text_input(
    "Jira Ticket ID (optional)",
    placeholder="e.g. DTSD-26188 — leave blank to test without a ticket",
    help="Leave blank to run cleaning only (no Jira post). Files are named by timestamp.",
).strip().upper()

col1, col2 = st.columns(2)
with col1:
    do_upload = st.checkbox("Upload to Files.com", value=True)
with col2:
    do_jira = st.checkbox("Post to Jira", value=True)

st.divider()

run_clicked = st.button("🚀 Run Pipeline", type="primary", use_container_width=True)

if run_clicked:
    if not uploaded_file:
        st.error("Please upload a file first.")
        st.stop()
    if ticket_id and not re.match(r"^[A-Z]+-\d+$", ticket_id):
        st.error("Ticket ID format should be like DTSD-26188 (or leave it blank).")
        st.stop()

    # No ticket → nothing to post to. Run cleaning only.
    if do_jira and not ticket_id:
        st.info("ℹ️ No ticket ID entered — skipping the Jira update and running cleaning only.")
    post_jira = do_jira and bool(ticket_id)

    try:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file, dtype=str).fillna("")
        else:
            df = pd.read_excel(uploaded_file, dtype=str).fillna("")
    except Exception as e:
        st.error(f"Could not read file: {e}")
        st.stop()

    st.info(f"📄 Loaded **{len(df):,} rows** from `{uploaded_file.name}`")

    with st.spinner("Running pipeline…"):
        cleaned_df, rejected_df, summary = run_pipeline(df, ticket_id, do_upload, post_jira)

    if summary is None:
        st.stop()

    # ── Results ────────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("✅ Pipeline Complete")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Input rows",    summary["input_rows"])
    m2.metric("Valid numbers", summary["cleaned_rows"])
    m3.metric("Rejected",      summary["rejected_rows"])
    m4.metric("Duplicates",    summary["duplicates"])

    if do_upload:
        if summary["files_path"]:
            st.success(f"📁 Uploaded: `{summary['files_path']}`")
        else:
            st.warning("📁 Files.com upload did not complete.")

    if post_jira:
        if summary["jira_url"]:
            st.success(f"🎫 Jira updated → [{ticket_id}]({summary['jira_url']})")
        else:
            st.warning("🎫 Jira comment did not post.")

    st.divider()
    dl1, dl2 = st.columns(2)
    with dl1:
        st.download_button(
            "⬇️ Download cleaned file",
            data=summary["clean_buf"].getvalue(),
            file_name=summary["clean_name"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    with dl2:
        if len(rejected_df) > 0:
            st.download_button(
                "⬇️ Download rejected log",
                data=summary["reject_buf"].getvalue(),
                file_name=summary["reject_name"],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.info("No rejections.")

    if len(rejected_df) > 0:
        with st.expander(f"🔍 View {len(rejected_df)} rejected rows"):
            st.dataframe(rejected_df, use_container_width=True)