from flask import Flask, render_template, request, redirect, session
from datetime import datetime, timezone, timedelta
from io import BytesIO
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from flask import send_file

app = Flask(__name__)
app.secret_key = 'nautique_merville_secret'

MOT_DE_PASSE_BILAN = 'BNM2026'

MOT_DE_PASSE_BAR = 'BNM2026BAR' 

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
    if not session.get('bar_ok'):
        return redirect('/login_bar')
    now = maintenant()
    for c in commandes:
        minutes_attente = int((now - c['heure']).total_seconds() / 60)
        c['attente'] = minutes_attente
    return render_template('bar.html', commandes=commandes)

@app.route('/login_bar', methods=['GET', 'POST'])
def login_bar():
    if request.method == 'POST':
        mdp = request.form.get('mot_de_passe', '')
        if mdp == MOT_DE_PASSE_BAR:
            session['bar_ok'] = True
            return redirect('/bar')
        else:
            return render_template('login_bar.html', erreur=True)
    return render_template('login_bar.html', erreur=False)

@app.route('/logout_bar')
def logout_bar():
    session.pop('bar_ok', None)
    return redirect('/login_bar')

@app.route('/prete/<int:commande_id>')
def commande_prete(commande_id):
    for c in commandes:
        if c['id'] == commande_id:
            c['statut'] = "Prête ! Passez au comptoir"
            c['heure_prete'] = maintenant()  # ← ajouter cette ligne
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

@app.route('/archiver-tout', methods=['POST'])
def archiver_tout():
    global commandes
    for c in commandes:
        c['statut'] = "Récupérée"
        historique.append(c)
    commandes = []
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

    # Temps moyen de préparation
temps_prep_list = []
for c in historique:
    if 'heure_prete' in c:
        duree = (c['heure_prete'] - c['heure']).total_seconds() / 60
        temps_prep_list.append(duree)
temps_moyen_prep = round(sum(temps_prep_list) / len(temps_prep_list), 1) if temps_prep_list else None

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


@app.route('/export-excel')
def export_excel():
    if not session.get('bilan_ok'):
        return redirect('/bilan')

    wb = openpyxl.Workbook()

    # ── Onglet 1 : Résumé ──
    ws1 = wb.active
    ws1.title = "Résumé"

    titre_font = Font(bold=True, size=13, color="FFFFFF")
    titre_fill = PatternFill("solid", fgColor="0056B3")
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="2C3E50")

    ws1.append(["Bilan du " + maintenant().strftime('%d/%m/%Y')])
    ws1['A1'].font = titre_font
    ws1['A1'].fill = titre_fill
    ws1.append([])
    ws1.append(["Indicateur", "Valeur"])
    for cell in ws1[3]:
        cell.font = header_font
        cell.fill = header_fill

    nb_commandes = len(historique)
    total_recettes = sum(c['total'] for c in historique)
    panier_moyen = round(total_recettes / nb_commandes, 2) if nb_commandes > 0 else 0

    stats_produits = {}
    commandes_par_heure = {}
    for c in historique:
        heure = c['heure'].strftime('%H:00')
        commandes_par_heure[heure] = commandes_par_heure.get(heure, 0) + 1
        for prod in c['produits']:
            stats_produits[prod] = stats_produits.get(prod, 0) + 1

    produit_star = max(stats_produits, key=stats_produits.get) if stats_produits else "—"
    heure_pointe = max(commandes_par_heure, key=commandes_par_heure.get) if commandes_par_heure else "—"

    ws1.append(["Nombre de commandes", nb_commandes])
    ws1.append(["Chiffre d'affaires (€)", total_recettes])
    ws1.append(["Panier moyen (€)", panier_moyen])
    ws1.append(["Produit star", produit_star])
    ws1.append(["Heure de pointe", heure_pointe])
    ws1.column_dimensions['A'].width = 28
    ws1.column_dimensions['B'].width = 20

    # ── Onglet 2 : Ventes par produit ──
    ws2 = wb.create_sheet("Ventes par produit")
    ws2.append(["Produit", "Quantité", "Recette (€)"])
    for cell in ws2[1]:
        cell.font = header_font
        cell.fill = header_fill
    for prod, qte in sorted(stats_produits.items(), key=lambda x: x[1], reverse=True):
        prix_unit = 0
        for cat in menu.values():
            for item in cat:
                if item['nom'] == prod or prod.endswith(item['nom']):
                    prix_unit = item['prix']
        ws2.append([prod, qte, round(qte * prix_unit, 2)])
    ws2.column_dimensions['A'].width = 40
    ws2.column_dimensions['B'].width = 12
    ws2.column_dimensions['C'].width = 15

    # ── Onglet 3 : Détail commandes ──
    ws3 = wb.create_sheet("Détail commandes")
    ws3.append(["#", "Heure", "Produits", "Note", "Total (€)"])
    for cell in ws3[1]:
        cell.font = header_font
        cell.fill = header_fill
    for c in sorted(historique, key=lambda x: x['heure']):
        ws3.append([
            f"#{c['id']:03d}",
            c['heure'].strftime('%H:%M'),
            ", ".join(c['produits']),
            c.get('note', ''),
            c['total']
        ])
    ws3.column_dimensions['A'].width = 8
    ws3.column_dimensions['B'].width = 10
    ws3.column_dimensions['C'].width = 50
    ws3.column_dimensions['D'].width = 20
    ws3.column_dimensions['E'].width = 12

    # Envoi du fichier
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f"bilan_{maintenant().strftime('%d-%m-%Y')}.xlsx"
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=filename)

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
