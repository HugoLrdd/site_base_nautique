from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime

app = Flask(__name__)

# Notre carte des produits (Le dictionnaire s'appelle 'menu' en minuscules)
menu = {
    "Boissons": [
        {"nom": "Perrier", "prix": 100},
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

# Listes pour gérer l'activité
commandes = []  # Commandes actives à l'écran du bar
historique = []  # Commandes terminées pour les stats du soir
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
        # Boucle ultra-robuste pour calculer le prix même si le nom inclut "Crêpe -" devant
        for prod in produits_choisis:
            for categorie in menu.values():
                for item in categorie:
                    # Vérifie si le nom du produit est contenu dans ce que le panier a envoyé
                    if item['nom'] == prod or prod.endswith(item['nom']):
                        total_commande += item['prix']
                        break

        # On crée un dictionnaire de commande ultra complet
        nouvelle_commande = {
            "id": compteur_ticket,
            "produits": produits_choisis,
            "heure": datetime.now(),  # Stocke l'heure de création
            "statut": "En préparation",  # Statut initial
            "total": total_commande
        }
        commandes.append(nouvelle_commande)
        compteur_ticket += 1
        
        # On redirige proprement vers l'URL de suivi
        return redirect(f'/suivi/{nouvelle_commande["id"]}')
    
    return redirect('/')

# Route pour que le client suive SA commande en direct
@app.route('/suivi/<int:commande_id>')
def suivi_commande(commande_id):
    # On cherche la commande dans les commandes actives
    commande = next((c for c in commandes if c['id'] == commande_id), None)
    
    # Si elle n'est plus active, on cherche dans l'historique
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

# Changer le statut d'une commande (En préparation -> Prête !)
@app.route('/prete/<int:commande_id>')
def commande_prete(commande_id):
    for c in commandes:
        if c['id'] == commande_id:
            c['statut'] = "Prête ! Passez au comptoir"
            break
    return redirect('/bar')

# Valider et archiver la commande (Suppression de l'écran + ajout aux statistiques)
@app.route('/archiver/<int:commande_id>')
def archiver_commande(commande_id):
    global commandes
    for c in commandes:
        if c['id'] == commande_id:
            c['statut'] = "Récupérée"
            historique.append(c)  # Sauvegarde pour le bilan
            break
    commandes = [c for c in commandes if c['id'] != commande_id]
    return redirect('/bar')

# Page du bilan pour ton père le soir
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

if __name__ == '__main__':
    app.run(debug=True)
