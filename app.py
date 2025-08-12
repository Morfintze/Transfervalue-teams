import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

def parse_marktwaarde(waarde):
    try:
        waarde = waarde.replace("€", "").replace(".", "").replace(",", ".").strip()
        if "mln" in waarde:
            return float(waarde.replace("mln", "").strip()) * 1_000_000
        elif "m" in waarde:
            return float(waarde.replace("m", "")) * 1_000_000
        elif "k" in waarde:
            return float(waarde.replace("k", "")) * 1_000
        else:
            return float(waarde)
    except ValueError:
        return 0

def zoek_team_marktwaarde_en_volgende_tegenstander(team_naam):
    if not team_naam:
        return None, "Vul een teamnaam in."

    encoded_team = quote(team_naam)
    zoek_url = f"https://www.transfermarkt.nl/schnellsuche/ergebnis/schnellsuche?query={encoded_team}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'nl-NL,nl;q=0.8,en-US;q=0.5,en;q=0.3',
        'Referer': 'https://www.transfermarkt.nl/'
    }

    def extract_marktwaarde(rij):
        mw_text = rij.find_all('td', {'class': 'rechts'})[-1].get_text(strip=True)
        return parse_marktwaarde(mw_text)

    try:
        zoek_response = requests.get(zoek_url, headers=headers)
        zoek_response.raise_for_status()
        zoek_soup = BeautifulSoup(zoek_response.text, 'html.parser')

        club_rijen = []
        for table in zoek_soup.find_all('table', {'class': 'items'}):
            for row in table.find_all('tr', {'class': ['odd', 'even']}):
                if row.find('a', href=True) and '/verein/' in row.find('a', href=True)['href']:
                    club_rijen.append(row)

        if not club_rijen:
            return None, "Geen club gevonden. Probeer een andere naam."

        club_rijen.sort(key=extract_marktwaarde, reverse=True)
        beste_club_rij = club_rijen[0]

        naam_td = beste_club_rij.find('td', {'class': 'hauptlink'})
        naam = naam_td.get_text(strip=True)
        club_link = naam_td.find('a', href=True)['href']
        marktwaarde = beste_club_rij.find_all('td', {'class': 'rechts'})[-1].get_text(strip=True)

        if '/verein/' in club_link:
            club_id = club_link.split('/verein/')[1].split('/')[0]
        else:
            return None, "Kon club ID niet extraheren."

        volledige_url = f"https://www.transfermarkt.nl{club_link}"

        club_response = requests.get(volledige_url, headers=headers)
        club_response.raise_for_status()
        club_soup = BeautifulSoup(club_response.text, 'html.parser')

        fav_voting = club_soup.find('div', {'class': 'fav-voting__wrapper'})

        if not fav_voting:
            return None, "Geen komende wedstrijd gevonden."

        teams = fav_voting.find_all('a', {'class': 'fav-voting__link-club'})

        if len(teams) != 2:
            return None, "Kon wedstrijdinformatie niet verwerken."

        team1 = teams[0].find('div', {'class': 'fav-voting__name'}).get_text(strip=True)
        team1_id = teams[0].find('img')['src'].split('/headerRund/')[1].split('.')[0]

        team2 = teams[1].find('div', {'class': 'fav-voting__name'}).get_text(strip=True)
        team2_id = teams[1].find('img')['src'].split('/headerRund/')[1].split('.')[0]

        tegenstander = team2 if club_id == team1_id else (team1 if club_id == team2_id else "Onbekende tegenstander")

        team_marktwaarden = {}
        for team in [team1, team2]:
            team_encoded = quote(team)
            team_url = f"https://www.transfermarkt.nl/schnellsuche/ergebnis/schnellsuche?query={team_encoded}"

            team_response = requests.get(team_url, headers=headers)
            team_response.raise_for_status()
            team_soup = BeautifulSoup(team_response.text, 'html.parser')

            team_rijen = []
            for table in team_soup.find_all('table', {'class': 'items'}):
                for row in table.find_all('tr', {'class': ['odd', 'even']}):
                    if row.find('a', href=True) and '/verein/' in row.find('a', href=True)['href']:
                        team_rijen.append(row)

            if team_rijen:
                team_rijen.sort(key=extract_marktwaarde, reverse=True)
                beste_team_rij = team_rijen[0]
                team_naam_td = beste_team_rij.find('td', {'class': 'hauptlink'})
                team_naam = team_naam_td.get_text(strip=True)
                team_marktwaarde = beste_team_rij.find_all('td', {'class': 'rechts'})[-1].get_text(strip=True)
                team_marktwaarden[team_naam] = parse_marktwaarde(team_marktwaarde)
            else:
                team_marktwaarden[team] = 0

        input_team_marktwaarde = team_marktwaarden.get(naam, 0)
        other_team_naam = team2 if naam == team1 else team1
        other_team_marktwaarde = team_marktwaarden.get(other_team_naam, 0)

        if input_team_marktwaarde == 0 or other_team_marktwaarde == 0:
            verhouding = None
        else:
            verhouding = input_team_marktwaarde / other_team_marktwaarde

        resultaat = {
            'team': naam,
            'marktwaarde': marktwaarde,
            'tegenstander': tegenstander,
            'wedstrijd': f"{team1} vs {team2}",
            'marktwaarde_team': input_team_marktwaarde,
            'marktwaarde_tegenstander': other_team_marktwaarde,
            'verhouding': verhouding,
            'club_url': volledige_url,
        }
        return resultaat, None

    except requests.exceptions.RequestException as e:
        return None, f"Verbindingsfout: {e}"
    except Exception as e:
        return None, f"Onverwachte fout: {str(e)}"

# --- Streamlit app ---

st.title("⚽ Team Marktwaarde & Volgende Tegenstander")

team_input = st.text_input("Voer een teamnaam in:", "")

if st.button("Zoek"):
    with st.spinner("Even zoeken..."):
        resultaat, fout = zoek_team_marktwaarde_en_volgende_tegenstander(team_input)

    if fout:
        st.error(fout)
    else:
        st.success(f"🏆 Team: {resultaat['team']}")
        st.write(f"💶 Totale marktwaarde: {resultaat['marktwaarde']}")
        st.write(f"🔗 [Clubpagina]({resultaat['club_url']})")
        st.write(f"🆚 Volgende wedstrijd: {resultaat['wedstrijd']}")
        st.write(f"   - Tegenstander: {resultaat['tegenstander']}")
        st.write(f"   - Marktwaarde {resultaat['team']}: €{resultaat['marktwaarde_team']:,}")
        st.write(f"   - Marktwaarde {resultaat['tegenstander']}: €{resultaat['marktwaarde_tegenstander']:,}")
        if resultaat['verhouding']:
            st.write(f"📊 Verhouding marktwaarde: {resultaat['verhouding']:.2f}")
        else:
            st.warning("Kan verhouding marktwaarde niet berekenen (missende data).")
