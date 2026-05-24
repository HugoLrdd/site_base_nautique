from flask import Flask, render_template, request, redirect, url_for, send_file, io
from datetime import datetime
# Importations pour le PDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

app = Flask(__name__)

# Exemple de dictionnaire pour simuler ta base de données de commandes
# S'il est vide au départ, c'est normal !
commandes = {}

# Ton dictionnaire de prix pour le calcul automatique côté serveur (sécurité)
PRIX_PRODUITS = {
    # Catégorie Boissons (Exemples - Ajuste avec tes vrais noms exacts et prix)
    "Coca-Cola": 2.50,
    "Ice Tea": 2.50,
    "Eau Minérale": 1.50,
    # Catégorie Crêpes
    "Crêpe Sucre": 3.00,
    "Crêpe Nutella": 3.50,
    # Catégorie Glaces
    "Glace Chocolat": 2.50,
    "Glace Vanille": 2.50,
    "Glace à l'eau": 2.00,
}

@app.route('/commander', methods=['POST'])
def commander():
    liste_produits = request.form.getlist('produits')
    
    if not liste_produits:
        return redirect(url_for('menu'))
    
    # 📐 CALCUL DU PRIX TOTAL CÔTÉ SERVEUR
    total = 0.0
    details_produits = []
    for nom in liste_produits:
        # On cherche le prix dans notre dictionnaire, sinon 0.0 par défaut
        prix = PRIX_PRODUITS.get(nom, 0.0)
        total += prix
        details_produits.append({"nom": nom, "prix": prix})

    # Génération d'un ID unique pour la commande (ex: basé sur l'heure ou un compteur)
    id_commande = str(int(datetime.now().timestamp()))
    
    # Sauvegarde complète de la commande
    commandes[id_commande] = {
        "id": id_commande,
        "date_heure": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "localisation": "Transat / Table", # Tu pourras l'ajuster si tu as un champ numéro de table
        "produits": details_produits,
        "total": total,
        "statut": "En attente"
    }
    
    return redirect(url_for('statut_client', id_commande=id_commande))

@app.route('/commande/<id_commande>')
def statut_client(id_commande):
    commande = commandes.get(id_commande)
    if not commande:
        return "Commande introuvable", 404
    return render_template('statut_client.html', commande=commande)

@app.route('/bar')
def espace_bar():
    # On transmet toutes les commandes au barman
    return render_template('bar.html', commandes=commandes.values())

# 🎫 LA ROUTE MAGIQUE QUI GÉNÈRE LE TICKET PDF
@app.route('/commande/<id_commande>/pdf')
def generer_pdf_recu(id_commande):
    commande = commandes.get(id_commande)
    if not commande:
        return "Commande introuvable", 404

    # Création d'un fichier temporaire en mémoire vive
    buffer = io.BytesIO()
    
    # Configuration du PDF (Format Ticket/Reçu vertical compact)
    doc = SimpleDocTemplate(buffer, pagesize=(300, 450), rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15)
    story = []
    
    styles = getSampleStyleSheet()
    style_titre = ParagraphStyle('Titre', parent=styles['Heading2'], alignment=1, spaceAfter=10)
    style_texte = ParagraphStyle('Texte', parent=styles['Normal'], fontSize=9, leading=12)
    style_texte_gras = ParagraphStyle('TexteGras', parent=styles['Normal'], fontSize=9, leading=12, fontName="Helvetica-Bold")
    
    # Contenu du ticket
    story.append(Paragraph("⛵ BASE NAUTIQUE DE MERVILLE", style_titre))
    story.append(Paragraph(f"<b>Date/Heure :</b> {commande['date_heure']}", style_texte))
    story.append(Paragraph(f"<b>Emplacement :</b> {commande['localisation']}", style_texte))
    story.append(Paragraph(f"<b>Commande N° :</b> {commande['id']}", style_texte))
    story.append(Spacer(1, 10))
    
    # Tableau des produits
    donnees_table = [[Paragraph("<b>Produit</b>", style_texte), Paragraph("<b>Prix</b>", style_texte)]]
    for p in commande['produits']:
        donnees_table.append([Paragraph(p['nom'], style_texte), Paragraph(f"{p['prix']:.2f} €", style_texte)])
    
    # Ligne du total
    donnees_table.append([Paragraph("<b>TOTAL À PAYER</b>", style_texte_gras), Paragraph(f"<b>{commande['total']:.2f} €</b>", style_texte_gras)])
    
    t = Table(donnees_table, colWidths=[180, 90])
    t.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('LINEBELOW', (0,0), (-1,0), 1, colors.black), # Ligne sous l'entête
        ('LINEABOVE', (0,-1), (-1,-1), 1, colors.black), # Ligne au dessus du total
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    
    story.append(t)
    story.append(Spacer(1, 20))
    story.append(Paragraph("Merci de votre visite ! Presentez ce recu au bar.", ParagraphStyle('Avis', parent=style_texte, alignment=1, fontName="Helvetica-Oblique")))
    
    doc.build(story)
    buffer.seek(0)
    
    return send_file(buffer, as_attachment=False, download_name=f"recu_{id_commande}.pdf", mime_type='application/pdf')
