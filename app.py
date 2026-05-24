from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime

app = Flask(__name__)

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
        {"nom": "Cornet Vanille", "prix": 2.50},
        {"nom": "Glace à l'eau", "prix": 1.50}
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
            "heure": datetime.now(),
            "statut": "En préparation",
            "total": total_commande
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
    maintenant = datetime.now()
    for c in commandes:
        minutes_attente = int((maintenant - c['heure']).total_seconds() / 60)
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

@app.route('/bilan')
def afficher_bilan():
    total_recettes = sum(c['total'] for c in historique)
    total_articles = 0
    stats_produits = {}

    for c in historique:
        for prod in c['produits']:
            total_articles += 1
            stats_produits[prod] = stats_produits.get(prod, 0) + 1

    return render_template('bilan.html', 
                           historique=historique, 
                           total_recettes=total_recettes, 
                           total_articles=total_articles,
                           stats_produits=stats_produits)

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
