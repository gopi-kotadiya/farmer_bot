from RAW.models.tool import Tool, ToolParam
from src.utils.database import get_connection
from src.utils.logger import logger

def update_farmer_profile(name=None, location=None, crops=None, email=None, session_id=""):
    """Tool to save or update farmer profile details in the database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Check if profile exists
        cursor.execute("SELECT id FROM farmers WHERE session_id = ?", (session_id,))
        exists = cursor.fetchone()
        
        if exists:
            # Update existing profile
            fields = []
            values = []
            if name: fields.append("name = ?"); values.append(name)
            if location: fields.append("location = ?"); values.append(location)
            if crops: fields.append("crops = ?"); values.append(crops)
            if email: fields.append("email = ?"); values.append(email)
            
            if fields:
                values.append(session_id)
                cursor.execute(f"UPDATE farmers SET {', '.join(fields)} WHERE session_id = ?", tuple(values))
                conn.commit()
                res = f"Profile updated for session {session_id}."
            else:
                res = "No fields provided to update."
        else:
            # Create new profile (telegram_id = session_id for email alerts lookup)
            cursor.execute(
                "INSERT INTO farmers (session_id, telegram_id, name, location, crops, email) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, session_id, name, location, crops, email),
            )
            conn.commit()
            res = f"New profile created for {name or 'Farmer'}."
        
        print(f"Profile Tool Called for Session: {session_id} -> Result: {res}")
        return res
    except Exception as e:
        return f"Database Error: {e}"
    finally:
        conn.close()

def get_farmer_profile(session_id=""):
    """Tool to retrieve farmer profile from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT name, location, crops, email FROM farmers WHERE session_id = ?",
            (session_id,),
        )
        profile = cursor.fetchone()
        if profile:
            data = dict(profile)
            em = data.get("email") or ""
            return (
                f"Farmer Name: {data['name']}, Location: {data['location']}, Crops: {data['crops']}, "
                f"Email: {em or '(not set)'}"
            )
        return "No profile found."
    finally:
        conn.close()

# Defining the Tools using the structured format
profile_update_tool = Tool(
    name="update_farmer_profile",
    description="Farmer ki details (Naam, Shehar, Fasal) save ya update karne ke liye use karein.",
    parameters=[
        ToolParam(name="name", type="string", description="Farmer ka naam", required=False),
        ToolParam(name="location", type="string", description="Shehar ka naam (City)", required=False),
        ToolParam(name="crops", type="string", description="Faslon ke naam (e.g. Wheat, Cotton)", required=False),
        ToolParam(
            name="email",
            type="string",
            description="Email — mausam/mandi/pest alerts yahi par aayengi",
            required=False,
        ),
    ],
    function=update_farmer_profile
)

profile_get_tool = Tool(
    name="get_farmer_profile",
    description="Farmer ki saved profile details read karne ke liye use karein.",
    parameters=[],
    function=get_farmer_profile
)
