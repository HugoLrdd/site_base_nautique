from flask import Flask, render_template, request, redirect
from datetime import datetime
import pytz
import sqlite3
import os

app = Flask(__name__)

# Configuration de la base de données SQLite
# On utilise un chemin absolu pour éviter les surprises sur Render
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bar_database.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Permet d'accéder aux colonnes par leur nom comme un dictionnaire
    return conn

def init_db():
    """Initialise la base de données au démarrage de l'application"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Table pour les commandes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commandes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            heure TEXT NOT NULL,
            statut TEXT NOT NULL,
            total REAL NOT NULL,
            note TEXT
        )
    ''')
    
    # Table pour les produits de chaque commande (Relation One-to-Many)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS produits_commande (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            commande_id INTEGER NOT NULL,
            nom_produit TEXT NOT NULL,
            FOREIGN KEY (commande_id) REFERENCES commandes (id) ON DELETE CASCADE
        )
    ''')
    
    # Table de configuration pour l'état du bar (ouvert/fermé)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS configuration (
            cle TEXT PRIMARY KEY,
            valeur TEXT NOT NULL
        )
    ''')
    
    # Insérer l'état initial du bar s'il n'existe pas déjà (ouvert par défaut)
    cursor.execute('''
        INSERT OR IGNORE INTO configuration (cle, valeur)
        VALUES ('bar_ouvert', 'true')
    ''')
    
    conn.commit()
    conn.close()

# Lancement de l'initialisation
init_db()

# Votre menu inchangé
menu = {
    "Boissons Chaudes": [
        {"nom": "Café", "prix": 1.50},
        {"nom": "Grand Café", "prix": 2.50},
        {"nom": "Thé / Infusion", "prix": 2.00},
        {"nom": "Chocolat Chaud", "prix": 2.50}
    ],
    "Softs": [
        {"nom": "Coca-Cola (33cl)", "prix": 2.50},
        {"nom": "Perrier (33cl)", "prix": 2.50},
        {"nom": "Oasis Oasis (33cl)", "prix": 2.50},
        {"nom": "Jus de fruits (25cl)", "prix": 2.00},
        {"nom": "Sirop à l'eau (25cl)", "prix": 1.50}
    ],
    "Bières & Cidre": [
        {"nom": "Pression Demi (25cl)", "prix": 3.00},
        {"nom": "Pression Pinte (50cl)", "prix": 5.50},
        {"nom": "Bière Bouteille (33cl)", "prix": 3.50},
        {"nom": "Cidre (33cl)", "prix": 3.00}
    ],
    "Snacks": [
        {"nom": "Chips", "prix": 1.50},
        {"nom": "Planche Apéro", "prix": 8.00},
        {"nom": "Gaufre / Crêpe", "prix": 3.00}
    ]
}

def maintenant():
    tz = pytz.timezone('Europe/Paris')
    return datetime.now(tz)

def calculer_attente(heure_str):
    try:
        tz = pytz.timezone('Europe/Paris')
        heure_commande = datetime.strptime(heure_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz)
        diff = maintenant() - heure_commande
        return int(diff.total_seconds() // 60)
    except:
        return 0

def is_bar_ouvert():
    conn = get_db_connection()
    res = conn.execute("SELECT valeur FROM configuration WHERE cle = 'bar_ouvert'").fetchone()
    conn.close()
    return res['valeur'] == 'true' if res else True

# --- ROUTES CLIENTS ---

@app.route('/')
def afficher_menu():
    if not is_bar_ouvert():
        return render_template('bar_ferme.html')
    return render_template('menu.html', menu=menu)

@app.route('/commander', methods=['POST'])
def prendre_commande():
    if not is_bar_ouvert():
        return render_template('bar_ferme.html')
        
    produits_choisis = request.form.getlist('produits')
    note = request.form.get('note', '').strip()

    if produits_choisis:
        total_commande = 0
        for prod in produits_choisis:
            for categorie in menu.values():
                for item in categorie:
                    if item['nom'] == prod or prod.endswith(item['nom']):
                        total_commande += item['prix']
                        break

        # Insertion SQL de la commande
        conn = get_db_connection()
        cursor = conn.cursor()
        heure_actuelle = maintenant().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute(
            "INSERT INTO commandes (heure, statut, total, note) VALUES (?, ?, ?, ?)",
            (heure_actuelle, "En préparation", total_commande, note)
        )
        commande_id = cursor.lastrowid
        
        # Insertion des produits associés
        for prod in produits_choisis:
            cursor.execute(
                "INSERT INTO produits_commande (commande_id, nom_produit) VALUES (?, ?)",
                (commande_id, prod)
            )
            
        conn.commit()
        conn.close()

        return redirect(f'/suivi/{commande_id}')

    return redirect('/')

@app.route('/suivi/<int:commande_id>')
def suivi_commande(commande_id):
    conn = get_db_connection()
    c = conn.execute("SELECT * FROM commandes WHERE id = ?", (commande_id,)).fetchone()
    
    if not c:
        conn.close()
        return "Commande introuvable", 404
        
    # Récupérer les produits
    produits_rows = conn.execute("SELECT nom_produit FROM produits_commande WHERE commande_id = ?", (commande_id,)).fetchall()
    conn.close()
    
    commande_dict = {
        "id": c["id"],
        "statut": c["statut"],
        "total": c["total"],
        "note": c["note"],
        "produits": [p["nom_produit"] for p in produits_rows]
    }
    
    return render_template('suivi.html', commande=commande_dict)

# --- ROUTES BAR / COMPTOIR ---

@app.route('/bar')
def ecran_bar():
    conn = get_db_connection()
    # On ne récupère que les commandes qui ne sont pas archivées/servies
    commandes_rows = conn.execute("SELECT * FROM commandes WHERE statut != 'Servie' ORDER BY id ASC").fetchall()
    
    commandes_actives = []
    for row in commandes_rows:
        produits_rows = conn.execute("SELECT nom_produit FROM produits_commande WHERE commande_id = ?", (row["id"],)).fetchall()
        
        commandes_actives.append({
            "id": row["id"],
            "heure": row["heure"],
            "statut": row["statut"],
            "total": row["total"],
            "note": row["note"],
            "attente": calculer_attente(row["heure"]),
            "produits": [p["nom_produit"] for p in produits_rows]
        })
        
    conn.close()
    return render_template('bar.html', commandes=commandes_actives, bar_ouvert=is_bar_ouvert())

@app.route('/toggle-bar', methods=['POST'])
def toggle_bar():
    conn = get_db_connection()
    nouvel_etat = "false" if is_bar_ouvert() else "true"
    conn.execute("UPDATE configuration SET valeur = ? WHERE cle = 'bar_ouvert'", (nouvel_etat,))
    conn.commit()
    conn.close()
    return redirect('/bar')

@app.route('/prete/<int:commande_id>')
def commande_prete(commande_id):
    conn = get_db_connection()
    conn.execute("UPDATE commandes SET statut = 'Prête !' WHERE id = ?", (commande_id,))
    conn.commit()
    conn.close()
    return redirect('/bar')

@app.route('/archiver/<int:commande_id>')
def archiver_commande(commande_id):
    conn = get_db_connection()
    conn.execute("UPDATE commandes SET statut = 'Servie' WHERE id = ?", (commande_id,))
    conn.commit()
    conn.close()
    return redirect('/bar')

@app.route('/archiver-tout', methods=['POST'])
def archiver_tout():
    conn = get_db_connection()
    conn.execute("UPDATE commandes SET statut = 'Servie' WHERE statut != 'Servie'")
    conn.commit()
    conn.close()
    return redirect('/bar')

@app.route('/recu/<int:commande_id>')
def voir_recu(commande_id):
    conn = get_db_connection()
    c = conn.execute("SELECT * FROM commandes WHERE id = ?", (commande_id,)).fetchone()
    if not c:
        conn.close()
        return "Commande introuvable", 404
    produits_rows = conn.execute("SELECT nom_produit FROM produits_commande WHERE commande_id = ?", (commande_id,)).fetchall()
    conn.close()
    
    commande_dict = {
        "id": c["id"],
        "heure": c["heure"],
        "total": c["total"],
        "produits": [p["nom_produit"] for p in produits_rows]
    }
    return render_template('suivi.html', commande=commande_dict)

@app.route('/logout_bar')
def logout_bar():
    return "Déconnexion réussie (Écran Bar clos)"

@app.route('/raz-compteur', methods=['POST'])
def raz_compteur():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. On supprime tous les produits des commandes
    cursor.execute("DELETE FROM produits_commande")
    # 2. On supprime toutes les commandes
    cursor.execute("DELETE FROM commandes")
    # 3. On remet le compteur interne de SQLite à zéro
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='commandes'")
    
    conn.commit()
    conn.close()
    return redirect('/bar')

if __name__ == '__main__':
    app.run(debug=True)
