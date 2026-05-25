from flask import Flask, render_template, request, redirect, session
from datetime import datetime
import pytz

app = Flask(__name__)
app.secret_key = "base_nautique_merville_secret_key_123"

# MOT DE PASSE POUR LE BILAN
MOT_DE_PASSE_BILAN = "admin"

# Données globales en mémoire (Structure d'origine)
commandes = []
historique = []
bar_ouvert = True

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
    for categorie, items in menu.items():
        for item in items:
            if item['nom'] == nom_produit or nom_produit.endswith(item['nom']):
                if "Crêpe" in item['nom']:
                    return "Crêpes"
                return categorie
    return "Autres"

def calculer_attente(heure_commande):
    diff = maintenant() - heure_commande
    return int(diff.total_seconds() // 60)


# --- ROUTES CLIENTS ---

@app.route('/')
def afficher_menu():
    global bar_ouvert
    if not bar_ouvert:
        return render_template('bar_ferme.html')
    return render_template('menu.html', menu=menu)

@app.route('/commander', methods=['POST'])
def prendre_commande():
    global bar_ouvert
    if not bar_ouvert:
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

        # ID auto-incrémenté basé sur l'historique + commandes en cours
        prochain_id = len(historique) + len(commandes) + 1
        
        nouvelle_commande = {
            "id": prochain_id,
            "heure": maintenant(),
            "heure_prete": None,
            "produits": produits_choisis,
            "statut": "En préparation",
            "total": total_commande,
            "note": note
        }
        commandes.append(nouvelle_commande)
        return redirect(f'/suivi/{nouvelle_commande["id"]}')

    return redirect('/')

@app.route('/suivi/<int:commande_id>')
def suivi_commande(commande_id):
    all_cmds = commandes + historique
    commande_trouvee = next((c for c in all_cmds if c['id'] == commande_id), None)
    if not commande_trouvee:
        return "Commande introuvable", 404
    return render_template('suivi.html', commande=commande_trouvee)


# --- ROUTES BAR / COMPTOIR ---

@app.route('/bar')
def ecran_bar():
    global bar_ouvert
    for c in commandes:
        c['attente'] = calculer_attente(c['heure'])
    return render_template('bar.html', commandes=commandes, bar_ouvert=bar_ouvert)

@app.route('/toggle-bar', methods=['POST'])
def toggle_bar():
    global bar_ouvert
    bar_ouvert = not bar_ouvert
    return redirect('/bar')

@app.route('/prete/<int:commande_id>')
def commande_prete(commande_id):
    commande = next((c for c in commandes if c['id'] == commande_id), None)
    if commande:
        commande['statut'] = "Prête !"
        commande['heure_prete'] = maintenant()
    return redirect('/bar')

@app.route('/archiver/<int:commande_id>')
def archiver_commande(commande_id):
    commande = next((c for c in commandes if c['id'] == commande_id), None)
    if commande:
        commande['statut'] = "Servie"
        if commande not in historique:
            historique.append(commande)
        commandes.remove(commande)
    return redirect('/bar')


# --- ROUTE BILAN ET STATISTIQUES ---

@app.route('/bilan', methods=['GET', 'POST'])
def afficher_bilan():
    if request.method == 'POST':
        mdp_saisi = request.form.get('mot_de_passe')
        if mdp_saisi == MOT_DE_PASSE_BILAN:
            session['bilan_connecte'] = True
        else:
            return render_template('login_bilan.html', erreur=True)

    if not session.get('bilan_connecte'):
        return render_template('login_bilan.html', erreur=False)

    # Calculs statistiques sur l'historique des commandes passées
    total_recettes = sum(c['total'] for c in historique)
    nb_commandes = len(historique)
    panier_moyen = total_recettes / nb_commandes if nb_commandes > 0 else 0.0

    stats_produits = {}
    stats_categories = {}
    commandes_par_heure = {}
    total_temps_prep = 0
    nb_commandes_pretes = 0

    for c in historique:
        for prod in c['produits']:
            stats_produits[prod] = stats_produits.get(prod, 0) + 1
            cat = trouver_categorie(prod)
            stats_categories[cat] = stats_categories.get(cat, 0) + 1

        cle_heure = c['heure'].strftime("%Hh")
        commandes_par_heure[cle_heure] = commandes_par_heure.get(cle_heure, 0) + 1

        if c['heure_prete']:
            diff_minutes = (c['heure_prete'] - c['heure']).total_seconds() / 60
            total_temps_prep += diff_minutes
            nb_commandes_pretes += 1

    total_articles = sum(stats_produits.values())
    produit_star = max(stats_produits, key=stats_produits.get) if stats_produits else None
    heure_pointe = max(commandes_par_heure, key=commandes_par_heure.get) if commandes_par_heure else None
    temps_moyen_prep = int(total_temps_prep / nb_commandes_pretes) if nb_commandes_pretes > 0 else 0

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

@app.route('/reset', methods=['POST'])
def reset_total():
    global commandes, historique
    commandes = []
    historique = []
    return redirect('/bilan')

@app.route('/logout_bilan')
def logout_bilan():
    session.pop('bilan_connecte', None)
    return redirect('/bilan')

@app.route('/logout_bar')
def logout_bar():
    return redirect('/')

@app.route('/export-excel')
def export_excel():
    return "Export Excel non configuré", 200


if __name__ == '__main__':
    app.run(debug=True)
