import streamlit as st
import pandas as pd
from datetime import date
import sqlite3
from io import BytesIO

# -------------------------
# 1️⃣ Database Setup
# -------------------------
DB_FILE = "transactions.db"

# Connect to SQLite (creates file if not exist)
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
c = conn.cursor()

# Create table if it doesn't exist
c.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trans_date TEXT,
    description TEXT,
    income REAL,
    expenses REAL,
    balance REAL
)
""")
conn.commit()

# -------------------------
# Helper Functions
# -------------------------
def fetch_transactions():
    df = pd.read_sql("SELECT * FROM transactions ORDER BY trans_date ASC", conn)
    return df

def recalc_balance(df):
    """Recalculate running balance sequentially and update SQLite."""
    balance = 0
    balances = []
    for _, row in df.iterrows():
        balance += row["income"] - row["expenses"]
        balances.append(balance)
    df["balance"] = balances
    # Update SQLite balances
    for i, row in df.iterrows():
        c.execute("UPDATE transactions SET balance = ? WHERE id = ?", (row["balance"], row["id"]))
    conn.commit()
    return df

def add_transaction(trans_date, desc, income, expenses):
    last_balance = fetch_transactions()["balance"].iloc[-1] if not fetch_transactions().empty else 0
    new_balance = last_balance + income - expenses
    c.execute("""
        INSERT INTO transactions (trans_date, description, income, expenses, balance)
        VALUES (?, ?, ?, ?, ?)
    """, (trans_date, desc, income, expenses, new_balance))
    conn.commit()

def delete_transaction(row_id):
    c.execute("DELETE FROM transactions WHERE id = ?", (row_id,))
    conn.commit()

def update_transaction(row_id, trans_date, desc, income, expenses):
    c.execute("""
        UPDATE transactions
        SET trans_date = ?, description = ?, income = ?, expenses = ?
        WHERE id = ?
    """, (trans_date, desc, income, expenses, row_id))
    conn.commit()

def export_to_excel(df):
    """Convert DataFrame to Excel and return as BytesIO."""
    output = BytesIO()
    df.to_excel(output, index=False, sheet_name="Transactions")
    output.seek(0)
    return output

# -------------------------
# 2️⃣ Streamlit Layout
# -------------------------
st.set_page_config(page_title="Sam's Accounting App",page_icon="🏨", layout="wide")
st.title("🏨 Sam's Place Accounting App")
st.write("Record daily transactions and auto-calculate balance")

df = fetch_transactions()

# -------------------------
# 2️⃣1️⃣ Summary Panel
# -------------------------
if not df.empty:
    total_income = df["income"].sum()
    total_expenses = df["expenses"].sum()
    current_balance = df["balance"].iloc[-1]
else:
    total_income = total_expenses = current_balance = 0.0

col1, col2, col3 = st.columns(3)
col1.metric("Total Income", f"RM{total_income:,.2f}")
col2.metric("Total Expenses", f"RM{total_expenses:,.2f}")
col3.metric("Current Balance", f"RM{current_balance:,.2f}")

# -------------------------
# 3️⃣ Add Transaction
# -------------------------
st.subheader("➕ Add New Transaction")

# Initialize session state defaults (no conflict with widget keys)
if "trans_date" not in st.session_state:
    st.session_state.trans_date = date.today()
if "desc" not in st.session_state:
    st.session_state.desc = ""
if "Income" not in st.session_state:
    st.session_state.Income = 0.0
if "Expenses" not in st.session_state:
    st.session_state.Expenses = 0.0

with st.form("transaction_form"):
    trans_date = st.date_input("Date", key="trans_date")
    desc = st.text_input("Description", key="desc")
    income = st.number_input("Income", min_value=0.0, step=0.01, key="Income")
    expenses = st.number_input("Expenses", min_value=0.0, step=0.01, key="Expenses")
    submit = st.form_submit_button("Save Transaction")

if submit:
    if not desc.strip():
        st.warning("⚠️ Please enter a description.")
    elif income == 0 and expenses == 0:
        st.warning("⚠️ Either Income or Expenses must be greater than 0.")
    else:
        add_transaction(str(trans_date), desc, income, expenses)
        df = fetch_transactions()
        df = recalc_balance(df)
        st.success("✅ Transaction added successfully!")

# -------------------------
# 4️⃣ Display Transactions
# -------------------------
st.subheader("📊 Transaction History")
if not df.empty:
    st.dataframe(df[["id", "trans_date", "description", "income", "expenses", "balance"]], use_container_width=True)
else:
    st.info("No transactions recorded yet.")

# -------------------------
# 6️⃣ Export to Excel
# -------------------------
st.subheader("💾 Export Transactions to Excel")

if not df.empty:
    excel_data = export_to_excel(df)
    st.download_button(
        label="⏬ Download Excel",
        data=excel_data,
        file_name="transactions.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# -------------------------
# 5️⃣ Edit / Delete Transactions
# -------------------------
st.subheader("✏️ Edit / Delete Transaction")

if not df.empty:
    selected = st.selectbox(
        "Select transaction to edit/delete",
        [f"{row['id']}: {row['trans_date']} | {row['description']} | Income: {row['income']} | Expenses: {row['expenses']}"
         for _, row in df.iterrows()]
    )
    row_id = int(selected.split(":")[0])
    row_data = df[df["id"] == row_id].iloc[0]

    with st.form("edit_form"):
        new_date = st.date_input("Date", pd.to_datetime(row_data["trans_date"]).date(), key="edit_date")
        new_desc = st.text_input("Description", row_data["description"], key="edit_desc")
        new_income = st.number_input("Income", min_value=0.0, value=float(row_data["income"]), step=0.01, key="edit_income")
        new_expenses = st.number_input("Expenses", min_value=0.0, value=float(row_data["expenses"]), step=0.01, key="edit_expenses")
        save_edit = st.form_submit_button("Save Changes")

    if save_edit:
        if not new_desc.strip():
            st.warning("⚠️ Please enter a description.")
        elif new_income == 0 and new_expenses == 0:
            st.warning("⚠️ Either Income or Expenses must be greater than 0.")
        else:
            update_transaction(row_id, str(new_date), new_desc, new_income, new_expenses)
            df = fetch_transactions()
            df = recalc_balance(df)
            st.success("✅ Transaction updated successfully!")

    if st.button("🗑️ Delete Transaction"):
        delete_transaction(row_id)
        df = fetch_transactions()
        df = recalc_balance(df)
        st.success("🗑️ Transaction deleted successfully!")