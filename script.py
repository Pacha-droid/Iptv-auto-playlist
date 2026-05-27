import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Sources publiques globales bien ciblées
SOURCES_M3U = [
    "https://iptv-org.github.io/iptv/countries/fr.m3u",       # Chaînes Françaises
    "https://iptv-org.github.io/iptv/countries/dz.m3u",       # Chaînes Algériennes (DZ)
    "https://iptv-org.github.io/iptv/categories/sports.m3u"   # Sports Internationaux (BeIN, Al Kass...)
]

# Nombre de vérifications simultanées (ajustable selon votre connexion)
MAX_WORKERS = 30


def telecharger_et_filtrer():
    print("Extraction des bouquets (FR, DZ, Al Kass, BeIN Sports)...")
    flux_extraits = []

    for url in SOURCES_M3U:
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                lignes = response.text.splitlines()
                metadata = None

                for ligne in lignes:
                    if ligne.startswith("#EXTINF"):
                        metadata = ligne
                    elif ligne.startswith("http") and metadata:
                        nom_chaine_lower = metadata.lower()
                        url_flux = ligne

                        # --- CRITÈRES DE FILTRAGE DES BOUQUETS ---

                        # 1. Bouquet France
                        est_fr = "group-title=\"france\"" in nom_chaine_lower or "tvg-country=\"fr\"" in nom_chaine_lower

                        # 2. Bouquet Algérie (DZ)
                        est_dz = "group-title=\"algeria\"" in nom_chaine_lower or "tvg-country=\"dz\"" in nom_chaine_lower or "algérie" in nom_chaine_lower

                        # 3. Bouquet Al Kass Sport
                        est_kass = "kass" in nom_chaine_lower or "alkass" in nom_chaine_lower

                        # 4. Bouquet BeIN Sports (Toutes langues confondues pour secours)
                        est_bein = "bein" in nom_chaine_lower and "sport" in nom_chaine_lower

                        if est_fr or est_dz or est_kass or est_bein:
                            nom_propre = metadata.split(",")[-1].strip()

                            # Attribution dynamique du groupe pour ton lecteur IPTV
                            if est_fr:
                                groupe = "FRANCE"
                            elif est_dz:
                                groupe = "ALGERIE (DZ)"
                            elif est_kass:
                                groupe = "AL KASS SPORTS"
                            elif est_bein:
                                # On sépare le BeIN Arabe des autres langues pour s'y retrouver
                                if "ar" in nom_chaine_lower or "arabic" in nom_chaine_lower:
                                    groupe = "BeIN SPORTS (AR)"
                                else:
                                    groupe = "BeIN SPORTS (BACKUP LANG)"

                            flux_extraits.append({
                                "name": nom_propre,
                                "url": url_flux,
                                "group": groupe
                            })
                        metadata = None
        except Exception as e:
            print(f"Erreur lors de la lecture de {url} : {e}")

    return flux_extraits


def check_flux(chaine):
    """
    Vérification ultra-rapide (2 secondes max) pour éviter de bloquer le script.
    Retourne le dictionnaire de la chaîne si active, None sinon.
    """
    url = chaine["url"]
    try:
        res = requests.head(url, timeout=2, allow_redirects=True)
        if res.status_code == 200:
            return chaine
    except:
        pass
    try:
        res = requests.get(url, timeout=2, stream=True)
        if res.status_code == 200:
            return chaine
    except:
        pass
    return None


def verifier_flux_en_parallele(toutes_les_chaines):
    """
    Lance MAX_WORKERS vérifications simultanément au lieu d'une par une.
    Gain de temps : jusqu'à 30x plus rapide selon MAX_WORKERS.
    """
    chaines_valides = []
    urls_vues = set()

    # Dédoublonnage en amont pour ne pas lancer de vérifications inutiles
    chaines_uniques = []
    for ch in toutes_les_chaines:
        if ch["url"] not in urls_vues:
            urls_vues.add(ch["url"])
            chaines_uniques.append(ch)

    total = len(chaines_uniques)
    print(f"Vérification de {total} liens en parallèle ({MAX_WORKERS} simultanés)...\n")

    urls_vues.clear()  # Réinitialisation pour le suivi des valides

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Soumettre toutes les tâches en même temps
        futures = {executor.submit(check_flux, ch): ch for ch in chaines_uniques}

        compteur = 0
        for future in as_completed(futures):
            compteur += 1
            chaine_originale = futures[future]
            resultat = future.result()

            if resultat:
                statut = "[FONCTIONNE]"
                chaines_valides.append(resultat)
            else:
                statut = "[HS]"

            # Affichage de la progression en temps réel
            print(f"[{compteur}/{total}] [{chaine_originale['group']}] {chaine_originale['name']} -> {statut}")

    return chaines_valides


def main():
    toutes_les_chaines = telecharger_et_filtrer()
    print(f"\n{len(toutes_les_chaines)} liens potentiels trouvés. Nettoyage des chaînes hors ligne...\n")

    chaines_valides = verifier_flux_en_parallele(toutes_les_chaines)

    # Tri par groupe pour une playlist bien organisée
    chaines_valides.sort(key=lambda x: x["group"])

    # Écriture finale de la playlist organisée par groupes
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for ch in chaines_valides:
            f.write(f'#EXTINF:-1 tvg-name="{ch["name"]}" group-title="{ch["group"]}",{ch["name"]}\n')
            f.write(f'{ch["url"]}\n')

    print(f"\nFélicitations ! Votre playlist a été mise à jour avec {len(chaines_valides)} chaînes actives.")


if __name__ == "__main__":
    main()
