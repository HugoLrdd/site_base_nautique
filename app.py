from flask import Flask, render_template, request, redirect, session
from datetime import datetime, timedelta
import pytz
import sqlite3
import os

app = Flask(__name__)

# Clé secrète obligatoire pour faire fonctionner le système de connexion (session)
app.secret_key = "base_nautique_merville_secret_key_123"

# MOT DE PASSE POUR ACCÉDER AU BILAN (Modifiez-le ici si besoin !)
MOT_DE_PASSE_BILAN = "admin"

# Configuration de la base de données SQLite
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bar_database.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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
            heure_prete TEXT,
            statut TEXT NOT NULL,
            total REAL NOT NULL,
            note TEXT
        )
    ''')
    
    # Table pour les produits de chaque commande
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS produits_commande (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            commande_id INTEGER NOT NULL,
            nom_produit TEXT NOT NULL,
            FOREIGN KEY (commande_id) REFERENCES commandes (id) ON DELETE CASCADE
        )
    ''')
    
    # Table de configuration pour l'état du bar
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS configuration (
            cle TEXT PRIMARY KEY,
            valeur TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        INSERT OR IGNORE INTO configuration (cle, valeur)
        VALUES ('bar_ouvert', 'true')
    ''')
    
    conn.commit()
    conn.close()

init_db()

# Votre dictionnaire de menu d'origine
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
        {"nom": "Oasis (33cl)", "prix": 2.50},
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

def trouver_categorie(nom_produit):
    """Associe automatiquement un produit vendu à sa catégorie principale"""
    for categorie, items in menu.items():
        for item in items:
            if item['nom'] == nom_produit or nom_produit.endswith(item['nom']):
                # Ajustement pour correspondre aux styles du HTML ('Crêpes' ou 'Glaces')
                if "Crêpe" in item['nom']:
                    return "Crêpes"
                return categorie
    return "Autres"

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

        conn = get_db_connection()
        cursor = conn.cursor()
        heure_actuelle = maintenant().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute(
            "INSERT INTO commandes (heure, statut, total, note) VALUES (?, ?, ?, ?)",
            (heure_actuelle, "En préparation", total_commande, note)
        )
        commande_id = cursor.lastrowid
        
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
    heure_actuelle = maintenant().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("UPDATE commandes SET statut = 'Prête !', heure_prete = ? WHERE id = ?", (heure_actuelle, commande_id))
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


# --- ROUTE COMPLÈTE BILAN (LOGIN INCLUS) ---

@app.route('/bilan', methods=['GET', 'POST'])
def afficher_bilan():
    # Gestion de la soumission du mot de passe
    if request.method == 'POST':
        mdp_saisi = request.form.get('mot_de_passe')
        if mdp_saisi == MOT_DE_PASSE_BILAN:
            session['bilan_connecte'] = True
        else:
            return render_template('login_bilan.html', erreur=True)

    # Si le responsable n'est pas connecté, on lui montre l'écran de verrouillage
    if not session.get('bilan_connecte'):
        return render_template('login_bilan.html', erreur=False)

    # CALCULS DES STATISTIQUES AVEC SQLITE
    conn = get_db_connection()
    
    # 1. Nombre total de commandes et total recettes
    row_stats = conn.execute("SELECT COUNT(id) as nb, SUM(total) as ca FROM commandes").fetchone()
    nb_commandes = row_stats['nb'] if row_stats['nb'] is not None else 0
    total_recettes = row_stats['ca'] if row_stats['ca'] is not None else 0.0
    
    # 2. Panier Moyen
    panier_moyen = total_recettes / nb_commandes if nb_commandes > 0 else 0.0
    
    # 3. Récupération des articles et gestion des compteurs
    produits_rows = conn.execute("SELECT nom_produit FROM produits_commande").fetchall()
    total_articles = len(produits_rows)
    
    stats_produits = {}
    stats_categories = {}
    
    for row in produits_rows:
        nom = row['nom_produit']
        stats_produits[nom] = stats_produits.get(nom, 0) + 1
        
        cat = trouver_categorie(nom)
        stats_categories[cat] = stats_categories.get(cat, 0) + 1
        
    produit_star = max(stats_produits, key=stats_produits.get) if stats_produits else None
    
    # 4. Graphique horaire, temps moyen et historique des ventes
    commandes_rows = conn.execute("SELECT id, heure, heure_prete, total, note FROM commandes ORDER BY heure ASC").fetchall()
    
    commandes_par_heure = {}
    total_temps_prep = 0
    nb_commandes_pretes = 0
    historique = []
    
    for row in commandes_rows:
        dt_heure = datetime.strptime(row['heure'], "%Y-%m-%d %H:%M:%S")
        cle_heure = dt_heure.strftime("%Hh")
        commandes_par_heure[cle_heure] = commandes_par_heure.get(cle_heure, 0) + 1
        
        dt_prete = None
        if row['heure_prete']:
            dt_prete = datetime.strptime(row['heure_prete'], "%Y-%m-%d %H:%M:%S")
            diff_minutes = (dt_prete - dt_heure).total_seconds() / 60
            total_temps_prep += diff_minutes
            nb_commandes_pretes += 1
            
        # Charger les produits de cette commande spécifique pour l'historique
        p_rows = conn.execute("SELECT nom_produit FROM produits_commande WHERE commande_id = ?", (row['id'],)).fetchall()
        liste_p = [p['nom_produit'] for p in p_rows]
        
        historique.append({
            "id": row['id'],
            "heure": dt_heure,
            "heure_prete": dt_prete,
            "total": row['total'],
            "note": row['note'],
            "produits": liste_p
        })
        
    heure_pointe = max(commandes_par_heure, key=commandes_par_heure.get) if commandes_par_heure else None
    temps_moyen_prep = int(total_temps_prep / nb_commandes_pretes) if nb_commandes_pretes > 0 else 0

    conn.close()
    
    return render_template(
        'bilan.html',
        now=maintenant(),
        nb_commandes=nb_commandes,
        total_recettes=total_recettes,
        panier_moyen=panier_moyen,
        total_articles=total_articles,
        heure_pointe=heure_pointe,
        temps_moyen_prep=temps_moyen_prep,
        produit_star=produit_star,
        stats_produits=stats_produits,
        stats_categories=stats_categories,
        commandes_par_heure=commandes_par_heure,
        historique=historique,
        menu=menu
    )

# --- EFFACEMENT / RESET TOTAL ---

@app.route('/reset', methods=['POST'])
def reset_total():
    if not session.get('bilan_connecte'):
        return redirect('/bilan')
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM produits_commande")
    cursor.execute("DELETE FROM commandes")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='commandes'")
    conn.commit()
    conn.close()
    return redirect('/bilan')

# --- DECONNEXIONS ---

@app.route('/logout_bilan')
def logout_bilan():
    session.pop('bilan_connecte', None)
    return redirect('/bilan')

@app.route('/logout_bar')
def logout_bar():
    return redirect('/')

# --- EXPORT EXCEL ---
@app.route('/export-excel')
def export_excel():
    return "L'export Excel sera bientôt disponible avec SQLite.", 200


if __name__ == '__main__':
    app.run(debug=True)
