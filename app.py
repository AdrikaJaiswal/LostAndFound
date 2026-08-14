from flask import Flask, jsonify
from config import supabase

app = Flask(__name__)

@app.route('/')
def home():
    try:
        response = supabase.table('roles').select('*').execute()
        return jsonify({
            "status": "Success",
            "message": "Connected to Supabase successfully!",
            "roles": response.data
        })
    except Exception as e:
        return jsonify({"status": "Error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)