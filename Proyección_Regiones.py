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
    sys.stdout.write("\r" + " " * width)  # limpia línea
    sys.stdout.write("\r" + msg[:width])  # escribe sin pasarse
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

    total = len(departamentos) + 1

    for i, (nombre_dep, ubigeo) in enumerate(departamentos.items(), start=1):
        progreso(f"  [{i}/{total}] Consultando {nombre_dep.title()}...")

        try:
            url_cand = f"https://resultadoelectoral.onpe.gob.pe/presentacion-backend/eleccion-presidencial/participantes-ubicacion-geografica-nombre?tipoFiltro=ubigeo_nivel_01&idAmbitoGeografico=1&ubigeoNivel1={ubigeo}&idEleccion=10"
            url_actas = f"https://resultadoelectoral.onpe.gob.pe/presentacion-backend/resumen-general/totales?idAmbitoGeografico=1&idEleccion=10&tipoFiltro=ubigeo_nivel_01&idUbigeoDepartamento={ubigeo}"

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

            filas.append([
                nombre_dep.title(), actas,
                votos["Fujimori"], votos["Lopez"], votos["Sanchez"], votos["Nieto"],
                proy["Fujimori"], proy["Lopez"], proy["Sanchez"], proy["Nieto"]
            ])

        except Exception as e:
            print(f"\n  Error en {nombre_dep}: {e}")

    progreso(f"  [{total}/{total}] Consultando Extranjero...")
    try:
        url_cand_ext = "https://resultadoelectoral.onpe.gob.pe/presentacion-backend/eleccion-presidencial/participantes-ubicacion-geografica-nombre?tipoFiltro=ambito_geografico&idAmbitoGeografico=2&idEleccion=10"
        url_actas_ext = "https://resultadoelectoral.onpe.gob.pe/presentacion-backend/resumen-general/totales?idAmbitoGeografico=2&idEleccion=10&tipoFiltro=ambito_geografico"

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

        filas.append([
            "Extranjero", actas,
            votos["Fujimori"], votos["Lopez"], votos["Sanchez"], votos["Nieto"],
            proy["Fujimori"], proy["Lopez"], proy["Sanchez"], proy["Nieto"]
        ])

    except Exception as e:
        print(f"\n  Error en EXTRANJERO: {e}")

    progreso("")
    width = shutil.get_terminal_size().columns
    sys.stdout.write("\r" + " " * width + "\r")
    print("  Consultas finalizadas.\n")

    url_total = "https://resultadoelectoral.onpe.gob.pe/presentacion-backend/resumen-general/totales?idEleccion=10&tipoFiltro=eleccion"
    porcentaje_nacional = requests.get(url_total, headers=headers, timeout=12).json()["data"]["actasContabilizadas"]

    print(" " * 30 + "|" + f"Votos contados al {porcentaje_nacional:.3f}%".center(38) + "|" + "Votos proyectados al 100%".center(39))
    print(" " * 5 + "Región".ljust(14) + "Porcentaje | Fujimori    López   Sánchez    Nieto | Fujimori    López   Sánchez    Nieto")
    print(" " + "-" * 107)

    for i, row in enumerate(filas, start=1):
        ubic = str(row[0])
        if len(ubic) > 15:
            ubic = ubic[:12] + "..."
        
        print(
            f" {str(i).rjust(3)} {ubic.ljust(15)} "
            f"{row[1]:7.3f}% |"
            f"{int(row[2]):9} {int(row[3]):8} {int(row[4]):9} {int(row[5]):8} |"
            f"{int(row[6]):9} {int(row[7]):8} {int(row[8]):9} {int(row[9]):8}"
        )

    print(" " + "-" * 107)

    linea_cont = f"{int(tot_f_cont):8} {int(tot_l_cont):8} {int(tot_s_cont):9} {int(tot_n_cont):8}"
    linea_proy = f"{int(tot_f_proy):9} {int(tot_l_proy):8} {int(tot_s_proy):9} {int(tot_n_proy):8}"

    print(" " * 30 + "|" + "Votos contados acumulados".center(38) + "|" + "Votos proyectados acumulados".center(39))
    print(" " * 30 + "|" + " Fujimori    López   Sánchez    Nieto | Fujimori    López   Sánchez    Nieto")
    print(" " * 30 + "|" + f" {linea_cont} |{linea_proy}")

    print("\n\n  La proyección asume que la distribución de votos por región se mantiene constante.")
    print("  Hipótesis más confiable a mayor porcentaje de actas contabilizadas.\n")

while True:
    os.system('cls' if os.name == 'nt' else 'clear')
    ejecutar()
    input("  Presiona ENTER para actualizar...\n")