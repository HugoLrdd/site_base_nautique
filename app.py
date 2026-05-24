from flask import Flask, render_template, request, redirect, session
from datetime import datetime, timezone, timedelta

app = Flask(__name__)
app.secret_key = 'nautique_merville_secret'

MOT_DE_PASSE_BILAN = 'BNM2026'

def maintenant():
    return datetime.now(timezone.utc) + timedelta(hours=2)

menu = {
    "Boissons": [
        {"nom": "Coca-Cola", "prix": 2.50},
        {"nom": "Ice Tea", "prix": 2.50},
        {"nom": "Oasis", "prix": 2.50},
        {"nom": "Eau Minérale", "prix": 1.50}
    ],
    "Crêpes": [
        {"nom": "Sucre", "prix": 3.00},
        {"nom": "Nutella", "prix": 3.50},
        {"nom": "Confiture", "prix": 3.50}
    ],
    "Glaces": [
        {"nom": "Magnum", "prix": 3.00},
        {"nom": "Cornet Vanille", "prix": 2.50}
    ],
    "Planches": [
        {"nom": " Planche apéritif (saucisson,légume,jambon,cornichon,cacahuètes...)", "prix": 8.00},
        {"nom": " Planche charcuterie (saucisson,pâté,jambon,fromage,cacahuètes...)", "prix": 10.00},
        {"nom": " Planche fromage (brie,camembert,comté,pain,cacahuètes...)", "prix": 8.50}
    ]   
    
}

commandes = []
historique = []
compteur_ticket = 1

@app.route('/')
def afficher_menu():
    return render_template('menu.html', menu=menu)

@app.route('/commander', methods=['POST'])
def prendre_commande():
    global compteur_ticket
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

        nouvelle_commande = {
            "id": compteur_ticket,
            "produits": produits_choisis,
            "heure": maintenant(),
            "statut": "En préparation",
            "total": total_commande,
            "note": note
        }
        commandes.append(nouvelle_commande)
        compteur_ticket += 1

        return redirect(f'/suivi/{nouvelle_commande["id"]}')

    return redirect('/')

@app.route('/suivi/<int:commande_id>')
def suivi_commande(commande_id):
    commande = next((c for c in commandes if c['id'] == commande_id), None)
    if not commande:
        commande = next((c for c in historique if c['id'] == commande_id), None)
    if commande:
        return render_template('suivi.html', commande=commande)
    return "Commande introuvable", 404

@app.route('/bar')
def ecran_bar():
    now = maintenant()
    for c in commandes:
        minutes_attente = int((now - c['heure']).total_seconds() / 60)
        c['attente'] = minutes_attente
    return render_template('bar.html', commandes=commandes)

@app.route('/prete/<int:commande_id>')
def commande_prete(commande_id):
    for c in commandes:
        if c['id'] == commande_id:
            c['statut'] = "Prête ! Passez au comptoir"
            break
    return redirect('/bar')

@app.route('/archiver/<int:commande_id>')
def archiver_commande(commande_id):
    global commandes
    for c in commandes:
        if c['id'] == commande_id:
            c['statut'] = "Récupérée"
            historique.append(c)
            break
    commandes = [c for c in commandes if c['id'] != commande_id]
    return redirect('/bar')

@app.route('/bilan', methods=['GET', 'POST'])
def afficher_bilan():
    if request.method == 'POST' and 'mot_de_passe' in request.form:
        mdp = request.form.get('mot_de_passe', '')
        if mdp == MOT_DE_PASSE_BILAN:
            session['bilan_ok'] = True
        else:
            return render_template('login_bilan.html', erreur=True)

    if not session.get('bilan_ok'):
        return render_template('login_bilan.html', erreur=False)

    total_recettes = sum(c['total'] for c in historique)
    total_articles = 0
    stats_produits = {}
    stats_categories = {}
    nb_commandes = len(historique)

    panier_moyen = round(total_recettes / nb_commandes, 2) if nb_commandes > 0 else 0

    commandes_par_heure = {}
    for c in historique:
        heure = c['heure'].strftime('%H:00')
        commandes_par_heure[heure] = commandes_par_heure.get(heure, 0) + 1

    heure_pointe = None
    if commandes_par_heure:
        heure_pointe = max(commandes_par_heure, key=commandes_par_heure.get)

    for c in historique:
        for prod in c['produits']:
            total_articles += 1
            stats_produits[prod] = stats_produits.get(prod, 0) + 1
            for cat, items in menu.items():
                for item in items:
                    if item['nom'] == prod or prod.endswith(item['nom']):
                        stats_categories[cat] = stats_categories.get(cat, 0) + 1
                        break

    produit_star = max(stats_produits, key=stats_produits.get) if stats_produits else None
    commandes_par_heure_triees = dict(sorted(commandes_par_heure.items()))

    return render_template('bilan.html',
                           historique=historique,
                           total_recettes=total_recettes,
                           total_articles=total_articles,
                           stats_produits=stats_produits,
                           stats_categories=stats_categories,
                           panier_moyen=panier_moyen,
                           heure_pointe=heure_pointe,
                           nb_commandes=nb_commandes,
                           produit_star=produit_star,
                           commandes_par_heure=commandes_par_heure_triees,
                           now=maintenant(),
                           menu=menu)

@app.route('/reset', methods=['POST'])
def reset_bilan():
    global historique
    historique = []
    return redirect('/bilan')

@app.route('/logout_bilan')
def logout_bilan():
    session.pop('bilan_ok', None)
    return redirect('/bilan')

@app.route('/recu/<int:commande_id>')
def recu_commande(commande_id):
    commande = next((c for c in commandes if c['id'] == commande_id), None)
    if not commande:
        commande = next((c for c in historique if c['id'] == commande_id), None)
    if commande:
        return render_template('recu.html', commande=commande, menu=menu)
    return "Commande introuvable", 404

if __name__ == '__main__':
    app.run(debug=True)
