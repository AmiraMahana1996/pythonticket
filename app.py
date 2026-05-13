from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import pyodbc
import json
 
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
 
# ==========================================
# 1. DATABASE CONFIGURATION
# ==========================================
# Connection string using SQL Authentication
DB_CONNECTION_STRING = (
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=db52066.public.databaseasp.net,1433;" 
    "Database=db52066;"
    "UID=db52066;"
    "PWD=K_a7mN6=5q#C;"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
    "Timeout=30;"
)
 
# Specific Ticket IDs / Error Codes (Text fallback for the Subject line)
ERROR_DB_JSON = {
    "ERR-101": "It looks like you have a VPN profile mismatch. Please restart your Cisco AnyConnect client and click 'Update Profile'.",
    "ERR-102": "Your password has expired. Please visit https://portal.company.com/reset to create a new one.",
    "PRN-500": "The office printer is currently undergoing maintenance. Please route your print jobs to 'PRINTER-FLOOR-2'."
}
 
# ==========================================
# 2. DATABASE FUNCTIONS
# ==========================================
 
def get_db_connection():
    """Establishes a connection to SQL Server."""
    return pyodbc.connect(DB_CONNECTION_STRING)
 
def build_hierarchy_from_db():
    """Dynamically builds the nested JSON dropdown data from SQL Server."""
    hierarchy = {}
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
 
        # Query to join all 4 levels of the hierarchy
        query = """
            SELECT 
                d.Department, 
                sd.SubDep, 
                m.Modules, 
                sm.SubModule
            FROM DepTb d
            LEFT JOIN SubDepTb sd ON d.SN = sd.DepID
            LEFT JOIN ModulesTb m ON sd.SN = m.SubDepId
            LEFT JOIN SubModuleTb sm ON m.SN = sm.ModuleId
        """
        cursor.execute(query)
        rows = cursor.fetchall()
 
        for row in rows:
            dep, sub_dep, mod, sub_mod = row
 
            # Skip empty departments
            if not dep: continue
 
            if dep not in hierarchy:
                hierarchy[dep] = {}
 
            if sub_dep:
                if sub_dep not in hierarchy[dep]:
                    hierarchy[dep][sub_dep] = {}
 
                if mod:
                    if mod not in hierarchy[dep][sub_dep]:
                        hierarchy[dep][sub_dep][mod] = []
 
                    if sub_mod:
                        if sub_mod not in hierarchy[dep][sub_dep][mod]:
                            hierarchy[dep][sub_dep][mod].append(sub_mod)
 
        conn.close()
    except Exception as e:
        print(f"Error loading hierarchy: {e}")
 
    return hierarchy
 
def search_for_solution(dept, sub_dept, module, sub_module, subject, description):
    """1st checks the DB 'Resolvation' column. 2nd falls back to Error Codes in Text."""
 
    # 1. Check the database for the Module's explicit solution (Resolvation)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
 
        # We join the tables to ensure we get the Resolvation for the exact module selected
        query = """
            SELECT m.Resolvation 
            FROM ModulesTb m
            JOIN SubDepTb sd ON m.SubDepId = sd.SN
            JOIN DepTb d ON sd.DepID = d.SN
            WHERE d.Department = ? AND sd.SubDep = ? AND m.Modules = ?
        """
        cursor.execute(query, (dept, sub_dept, module))
        result = cursor.fetchone()
        conn.close()
 
        if result and result[0]:
            return result[0] # Return the Resolvation text
 
    except Exception as e:
        print(f"Error searching for solution: {e}")
 
    # 2. Fallback check: Did they type a specific error code in the text?
    combined_text = f"{subject} {description}".upper()
    for ticket_id, solution in ERROR_DB_JSON.items():
        if ticket_id in combined_text:
            return solution
 
    # 3. If neither matches, return None
    return None
 
def save_ticket_to_db(ticket_data):
    """Saves issues directly into the SQL Server TicketingTb with Dynamic Status."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
 
        # UPDATED: We now grab the exact status sent by the ASP.NET Javascript
        # If no status is provided, it defaults to 'Open'
        ticket_status = ticket_data.get('status', 'Open')
 
        query = """
            INSERT INTO TicketingTb 
            (TicketDep, TicketSubDep, TicketModule, TicketSubModule, Subject, TicketDesc, TicketStatus,TicketSolvedBy,ResolvedOn,SubmiteedBy)
            VALUES (?, ?, ?, ?, ?, ?, ?,?,?,?)
        """
 
        cursor.execute(query, (
            ticket_data.get('department'), 
            ticket_data.get('sub_department'),
            ticket_data.get('module'),
            ticket_data.get('sub_module'),
            ticket_data.get('subject'),
            ticket_data.get('description'),
            ticket_status, 
             ticket_data.get('TicketSolvedBy'),
             ticket_data.get('ResolvedOn'),
              ticket_data.get('SubmiteedBy')
        ))
 
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"SQL Insert Error: {e}")
        return False
 
# ==========================================
# 3. FLASK ROUTES
# ==========================================
 
@app.route('/')
def index():
    return "Hello"
 
@app.route('/api/hierarchy', methods=['GET'])
def api_get_hierarchy():
    """Calls the database to generate the frontend dropdowns dynamically."""
    hierarchy_data = build_hierarchy_from_db()
    return jsonify(hierarchy_data)
 
@app.route('/api/check_solution', methods=['POST'])
def api_check_solution():
    """Step 1: Just checks if a solution exists based on dropdowns & text."""
    data = request.json
 
    dept = data.get('department')
    sub_dept = data.get('sub_department')
    module = data.get('module')
    sub_module = data.get('sub_module')
    subject = data.get('subject', '')
    description = data.get('description', '')
 
    solution = search_for_solution(dept, sub_dept, module, sub_module, subject, description)
 
    if solution:
        return jsonify({"found": True, "solution": solution})
    else:
        return jsonify({"found": False})
 
@app.route('/api/submit', methods=['POST'])
def api_submit_ticket():
    """Step 2: Saves the ticket to the SQL Server database."""
    data = request.json
    success = save_ticket_to_db(data)
 
    if success:
        # Note: We just send 'success' back. The JavaScript file handles showing the user 
        # the correct message based on if it was resolved or escalated.
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": "❌ Failed to save the ticket to the database."})
 
 
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)