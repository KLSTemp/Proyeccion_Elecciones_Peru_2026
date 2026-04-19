import requests
from datetime import datetime
import sys
import os
import shutil

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://resultadoelectoral.onpe.gob.pe/main/presidenciales",
    "Origin": "https://resultadoelectoral.onpe.gob.pe",
    "sec-fetch-site": "same-origin",
    "sec-fetch-mode": "cors"
}

codigos_deseados = {"8", "10", "35", "16"}

mapa = {
    "8": "Fujimori",
    "10": "Sanchez",
    "35": "Lopez",
    "16": "Nieto"
}

def progreso(msg):
    width = shutil.get_terminal_size().columns
    msg = msg[:width-1]
    sys.stdout.write("\r" + " " * width)
    sys.stdout.write("\r" + msg)
    sys.stdout.flush()

def obtener_votos(data_cand):
    votos_dict = {"Fujimori": 0, "Lopez": 0, "Sanchez": 0, "Nieto": 0}
    for c in data_cand.get("data", []):
        codigo = c.get("codigoAgrupacionPolitica")
        if codigo in codigos_deseados:
            votos_dict[mapa[codigo]] = c.get("totalVotosValidos", 0)
    return votos_dict

def ejecutar():

    filas = []

    tot_f_cont = tot_l_cont = tot_s_cont = tot_n_cont = 0
    tot_f_proy = tot_l_proy = tot_s_proy = tot_n_proy = 0

    url_dep = "https://resultadoelectoral.onpe.gob.pe/presentacion-backend/ubigeos/departamentos?idEleccion=10&idAmbitoGeografico=1"
    data_dep = requests.get(url_dep, headers=headers, timeout=25).json()
    departamentos = {d["nombre"]: d["ubigeo"] for d in data_dep["data"]}

    timestamp = datetime.now().strftime('%d/%m/%y %I:%M %p')
    print(f"\n  Solicitando data de 'https://resultadoelectoral.onpe.gob.pe/' ({timestamp}).\n")

    provincias_cache = {}
    total_provincias = 0

    for dep_nombre, dep_ubigeo in departamentos.items():
        url_prov = f"https://resultadoelectoral.onpe.gob.pe/presentacion-backend/ubigeos/provincias?idEleccion=10&idAmbitoGeografico=1&idUbigeoDepartamento={dep_ubigeo}"
        data_prov = requests.get(url_prov, headers=headers, timeout=25).json()
        provincias_cache[dep_ubigeo] = data_prov["data"]
        total_provincias += len(data_prov["data"])

    try:
        url_continentes = "https://resultadoelectoral.onpe.gob.pe/presentacion-backend/ubigeos/departamentos?idEleccion=10&idAmbitoGeografico=2"
        data_continentes = requests.get(url_continentes, headers=headers, timeout=25).json()
        num_continentes = len(data_continentes.get("data", []))
    except:
        num_continentes = 5

    total_general = total_provincias + num_continentes
    contador = 0

    for dep_nombre, dep_ubigeo in departamentos.items():
        for prov in provincias_cache[dep_ubigeo]:
            contador += 1
            prov_nombre = prov["nombre"]
            prov_ubigeo = prov["ubigeo"]

            progreso(f"  [{contador}/{total_general}] Consultando {dep_nombre.title()} - {prov_nombre.title()}...")

            try:
                url_cand = f"https://resultadoelectoral.onpe.gob.pe/presentacion-backend/eleccion-presidencial/participantes-ubicacion-geografica-nombre?tipoFiltro=ubigeo_nivel_02&idAmbitoGeografico=1&ubigeoNivel1={dep_ubigeo}&ubigeoNivel2={prov_ubigeo}&idEleccion=10"
                url_actas = f"https://resultadoelectoral.onpe.gob.pe/presentacion-backend/resumen-general/totales?idAmbitoGeografico=1&idEleccion=10&tipoFiltro=ubigeo_nivel_02&idUbigeoDepartamento={dep_ubigeo}&idUbigeoProvincia={prov_ubigeo}"

                data_cand = requests.get(url_cand, headers=headers, timeout=25).json()
                data_actas = requests.get(url_actas, headers=headers, timeout=25).json()

                actas = float(data_actas["data"]["actasContabilizadas"])
                votos = obtener_votos(data_cand)

                tot_f_cont += votos["Fujimori"]
                tot_l_cont += votos["Lopez"]
                tot_s_cont += votos["Sanchez"]
                tot_n_cont += votos["Nieto"]

                proy = {k: round(v / actas * 100) if actas > 0 else 0 for k, v in votos.items()}

                tot_f_proy += proy["Fujimori"]
                tot_l_proy += proy["Lopez"]
                tot_s_proy += proy["Sanchez"]
                tot_n_proy += proy["Nieto"]

                filas.append([f"{dep_nombre.title()} - {prov_nombre.title()}", actas,
                              votos["Fujimori"], votos["Lopez"], votos["Sanchez"], votos["Nieto"],
                              proy["Fujimori"], proy["Lopez"], proy["Sanchez"], proy["Nieto"]])

            except Exception as e:
                print(f"\n  Error en {dep_nombre} - {prov_nombre}: {e}")

    try:
        url_continentes = "https://resultadoelectoral.onpe.gob.pe/presentacion-backend/ubigeos/departamentos?idEleccion=10&idAmbitoGeografico=2"
        data_continentes = requests.get(url_continentes, headers=headers, timeout=25).json()
        continentes = data_continentes["data"]

        for cont in continentes:
            cont_nombre = cont["nombre"]
            cont_ubigeo = cont["ubigeo"]

            contador += 1
            progreso(f"  [{contador}/{total_general}] Consultando Extranjero - {cont_nombre.title()}...")

            try:
                url_cand_ext = f"https://resultadoelectoral.onpe.gob.pe/presentacion-backend/eleccion-presidencial/participantes-ubicacion-geografica-nombre?tipoFiltro=ubigeo_nivel_01&idAmbitoGeografico=2&ubigeoNivel1={cont_ubigeo}&idEleccion=10"
                url_actas_ext = f"https://resultadoelectoral.onpe.gob.pe/presentacion-backend/resumen-general/totales?idAmbitoGeografico=2&idEleccion=10&tipoFiltro=ubigeo_nivel_01&idUbigeoDepartamento={cont_ubigeo}"

                data_cand = requests.get(url_cand_ext, headers=headers, timeout=25).json()
                data_actas = requests.get(url_actas_ext, headers=headers, timeout=25).json()

                actas = float(data_actas["data"]["actasContabilizadas"])
                votos = obtener_votos(data_cand)

                tot_f_cont += votos["Fujimori"]
                tot_l_cont += votos["Lopez"]
                tot_s_cont += votos["Sanchez"]
                tot_n_cont += votos["Nieto"]

                proy = {k: round(v / actas * 100) if actas > 0 else 0 for k, v in votos.items()}

                tot_f_proy += proy["Fujimori"]
                tot_l_proy += proy["Lopez"]
                tot_s_proy += proy["Sanchez"]
                tot_n_proy += proy["Nieto"]

                filas.append([f"Extranjero - {cont_nombre.title()}", actas,
                              votos["Fujimori"], votos["Lopez"], votos["Sanchez"], votos["Nieto"],
                              proy["Fujimori"], proy["Lopez"], proy["Sanchez"], proy["Nieto"]])

            except Exception as e:
                print(f"\n  Error en EXTRANJERO - {cont_nombre}: {e}")

    except Exception as e:
        print(f"\n  Error al obtener continentes: {e}")

    progreso("")
    width = shutil.get_terminal_size().columns
    sys.stdout.write("\r" + " " * width + "\r")
    print("  Consultas finalizadas.\n")

    url_total = "https://resultadoelectoral.onpe.gob.pe/presentacion-backend/resumen-general/totales?idEleccion=10&tipoFiltro=eleccion"
    porcentaje_nacional = requests.get(url_total, headers=headers, timeout=12).json()["data"]["actasContabilizadas"]

    print(" " * 52 + "|" + f"Votos contados al {porcentaje_nacional:.3f}%".center(37) + "|" + "Votos proyectados al 100%".center(37))
    print(" ".ljust(6)+ "Región - Provincia".ljust(35) + "Porcentaje |" + "Fujimori".rjust(9) + "López".rjust(9) + "Sánchez".rjust(9) + "Nieto".rjust(9) + " |" + "Fujimori".rjust(9) + "López".rjust(9) + "Sánchez".rjust(9) + "Nieto".rjust(9))
    print(" " + "-" * 127)

    for i, row in enumerate(filas, start=1):
        ubicacion = str(row[0])
        if len(ubicacion) > 38:
            ubicacion = ubicacion[:35] + "..."
        ubicacion = ubicacion.ljust(38)
        actas_str = f"{row[1]:.3f}%".rjust(9)

        cont = [f"{int(row[2]):>9}", f"{int(row[3]):>9}", f"{int(row[4]):>9}", f"{int(row[5]):>9}"]
        proy = [f"{int(row[6]):>9}", f"{int(row[7]):>9}", f"{int(row[8]):>9}", f"{int(row[9]):>9}"]

        print(f"  {str(i).rjust(3)} {str(row[0])[:35].ljust(35)} {actas_str} |{''.join(cont)} |{''.join(proy)}")

    print(" " + "-" * 127)

    linea_cont = f"{int(tot_f_cont):>8}{int(tot_l_cont):>9}{int(tot_s_cont):>9}{int(tot_n_cont):>9}"
    linea_proy = f"{int(tot_f_proy):>9}{int(tot_l_proy):>9}{int(tot_s_proy):>9}{int(tot_n_proy):>9}"

    print(" " * 52 + "|" + "Votos contados acumulados".center(37) + "|" + "Votos proyectados acumulados".center(37))
    print(" " * 52 + "| Fujimori    López  Sánchez    Nieto | Fujimori    López  Sánchez    Nieto")
    print(" " * 52 + f"| {linea_cont} |{linea_proy}")

    print("\n\n  La proyección asume que la distribución de votos por provincia o continente se mantiene constante.")
    print("  Hipótesis más confiable a mayor porcentaje de actas contabilizadas.\n")

while True:
    os.system('cls' if os.name == 'nt' else 'clear')
    ejecutar()
    input("\n  Presiona ENTER para actualizar...\n")