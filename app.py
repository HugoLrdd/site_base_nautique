from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Le vrai menu de la base nautique classé par catégories
MENU = {
    "Boissons": [
        {"nom": "Coca-Cola (33cl)", "prix": 2.50},
        {"nom": "Ice Tea Pêche (33cl)", "prix": 2.50},
        {"nom": "Eau minérale (50cl)", "prix": 1.50},
        {"nom": "Sirop à l'eau (Fraise/Menthe)", "prix": 1.20},
    ],
    "Glaces": [
        {"nom": "Cône Vanille/Chocolat", "prix": 2.50},
        {"nom": "Bâtonnet Fraise", "prix": 2.00},
        {"nom": "Glace à l'eau (Fusée)", "prix": 1.50},
    ],
    "Encas": [
        {"nom": "Sandwich Jambon-Beurre", "prix": 4.00},
        {"nom": "Paquet de Chips", "prix": 1.50},
        {"nom": "Gaufre au sucre", "prix": 2.50},
        {"nom": "Crêpe au Nutella", "prix": 3.00},
    ]
}

# La liste qui va stocker les commandes des clients en mémoire
COMMANDES = []
compteur_commande = 1

@app.route('/')
def page_menu():
    return render_template('menu.html', menu=MENU)

@app.route('/commander', methods=['POST'])
def passer_commande():
    global compteur_commande
    data = request.json
    
    if not data or 'panier' not in data:
        return jsonify({"erreur": "Panier vide"}), 400
        
    nouvelle_commande = {
        "numero": f"#{compteur_commande:03d}",
        "articles": data['panier'],
        "total": data['total']
    }
    
    COMMANDES.append(nouvelle_commande)
    compteur_commande += 1
    
    return jsonify({"statut": "succes", "numero": nouvelle_commande["numero"]})

@app.route('/bar')
def page_bar():
    return render_template('bar.html', commandes=COMMANDES)

@app.route('/supprimer/<numero>', methods=['POST'])
def supprimer_commande(numero):
    global COMMANDES
    COMMANDES = [cmd for cmd in COMMANDES if cmd['numero'] != numero]
    return jsonify({"statut": "succes"})

if __name__ == '__main__':
    app.run(debug=True)