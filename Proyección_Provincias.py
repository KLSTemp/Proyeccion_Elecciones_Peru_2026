import asyncio
import aiohttp
from datetime import datetime
import sys
import os
import shutil
import json

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://resultadoelectoral.onpe.gob.pe/main/presidenciales",
    "Origin": "https://resultadoelectoral.onpe.gob.pe",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
}

codigos_deseados = {"35", "10"}
mapa = {"35": "Lopez", "10": "Sanchez"}

semaphore = asyncio.Semaphore(5)

def progreso(msg):
    width = shutil.get_terminal_size().columns
    msg = msg[:width-1]
    sys.stdout.write("\r" + " " * width)
    sys.stdout.write("\r" + msg)
    sys.stdout.flush()

def obtener_votos(data_cand):
    votos_dict = {"Lopez": 0, "Sanchez": 0}
    for c in data_cand.get("data", []):
        codigo = c.get("codigoAgrupacionPolitica")
        if codigo in codigos_deseados:
            votos_dict[mapa.get(codigo)] = c.get("totalVotosValidos", 0)
    return votos_dict

async def fetch_json(session, url, retries=3):
    for intento in range(retries):
        try:
            async with semaphore:
                async with session.get(url, headers=headers, timeout=20) as resp:
                    if resp.status != 200:
                        await asyncio.sleep(0.5 * (intento + 1))
                        continue
                    try:
                        return await resp.json()
                    except:
                        text = await resp.text()
                        if text.strip().startswith(('{', '[')):
                            return json.loads(text)
        except Exception as e:
            if intento == retries - 1:
                print(f"\n  Error final en fetch: {url}\n   {e}")
                return None
        await asyncio.sleep(0.6 * (intento + 1))
    return None

async def procesar_provincia(session, dep_nombre, dep_ubigeo, prov):
    prov_nombre = prov["nombre"]
    prov_ubigeo = prov["ubigeo"]

    try:
        url_cand = f"https://resultadoelectoral.onpe.gob.pe/presentacion-backend/eleccion-presidencial/participantes-ubicacion-geografica-nombre?tipoFiltro=ubigeo_nivel_02&idAmbitoGeografico=1&ubigeoNivel1={dep_ubigeo}&ubigeoNivel2={prov_ubigeo}&idEleccion=10"
        url_actas = f"https://resultadoelectoral.onpe.gob.pe/presentacion-backend/resumen-general/totales?idAmbitoGeografico=1&idEleccion=10&tipoFiltro=ubigeo_nivel_02&idUbigeoDepartamento={dep_ubigeo}&idUbigeoProvincia={prov_ubigeo}"

        data_cand, data_actas = await asyncio.gather(
            fetch_json(session, url_cand),
            fetch_json(session, url_actas)
        )

        if not data_cand or not data_actas:
            print(f"  Falló provincia: {dep_nombre} - {prov_nombre}")
            return None

        actas = float(data_actas["data"]["actasContabilizadas"])
        votos = obtener_votos(data_cand)

        proy = {k: round(v / actas * 100) if actas > 0 else 0 for k, v in votos.items()}

        return {
            "ubicacion": f"{dep_nombre.title()} - {prov_nombre.title()}",
            "actas": actas,
            "votos": votos,
            "proy": proy
        }
    except Exception as e:
        print(f"  Error provincia {dep_nombre} - {prov_nombre}: {e}")
        return None

async def procesar_continente(session, cont):
    cont_nombre = cont["nombre"]
    cont_ubigeo = cont["ubigeo"]

    try:
        url_cand = f"https://resultadoelectoral.onpe.gob.pe/presentacion-backend/eleccion-presidencial/participantes-ubicacion-geografica-nombre?tipoFiltro=ubigeo_nivel_01&idAmbitoGeografico=2&ubigeoNivel1={cont_ubigeo}&idEleccion=10"
        url_actas = f"https://resultadoelectoral.onpe.gob.pe/presentacion-backend/resumen-general/totales?idAmbitoGeografico=2&idEleccion=10&tipoFiltro=ubigeo_nivel_01&idUbigeoDepartamento={cont_ubigeo}"

        data_cand, data_actas = await asyncio.gather(
            fetch_json(session, url_cand),
            fetch_json(session, url_actas)
        )

        if not data_cand or not data_actas:
            print(f"  Falló continente: {cont_nombre}")
            return None

        actas = float(data_actas["data"]["actasContabilizadas"])
        votos = obtener_votos(data_cand)
        proy = {k: round(v / actas * 100) if actas > 0 else 0 for k, v in votos.items()}

        return {
            "ubicacion": f"Extranjero - {cont_nombre.title()}",
            "actas": actas,
            "votos": votos,
            "proy": proy
        }

    except Exception as e:
        print(f"  Error continente {cont_nombre}: {e}")
        return None

async def main():
    async with aiohttp.ClientSession() as session:

        data_dep = await fetch_json(session, "https://resultadoelectoral.onpe.gob.pe/presentacion-backend/ubigeos/departamentos?idEleccion=10&idAmbitoGeografico=1")

        if not data_dep or "data" not in data_dep:
            print("  Error obteniendo departamentos")
            return

        departamentos = {d["nombre"]: d["ubigeo"] for d in data_dep["data"]}

        provincias_cache = {}
        total_provincias = 0
        tasks_prov = [fetch_json(session, f"https://resultadoelectoral.onpe.gob.pe/presentacion-backend/ubigeos/provincias?idEleccion=10&idAmbitoGeografico=1&idUbigeoDepartamento={ubigeo}") 
                      for ubigeo in departamentos.values()]

        prov_results = await asyncio.gather(*tasks_prov)
        for (dep_nombre, dep_ubigeo), data in zip(departamentos.items(), prov_results):
            if not data or "data" not in data:
                print(f"  Error obteniendo provincias de {dep_nombre}")
                provincias_cache[dep_ubigeo] = []
                continue

            provincias_cache[dep_ubigeo] = data["data"]
            total_provincias += len(data["data"])

        data_cont = await fetch_json(session, "https://resultadoelectoral.onpe.gob.pe/presentacion-backend/ubigeos/departamentos?idEleccion=10&idAmbitoGeografico=2")
        continentes = data_cont.get("data", [])

        timestamp = datetime.now().strftime('%d/%m/%y %I:%M %p')
        print(f"\n  > Consultando 'https://resultadoelectoral.onpe.gob.pe/' ({timestamp}).\n")

        tasks = []
        for dep_nombre, dep_ubigeo in departamentos.items():
            for prov in provincias_cache[dep_ubigeo]:
                tasks.append(procesar_provincia(session, dep_nombre, dep_ubigeo, prov))

        for cont in continentes:
            tasks.append(procesar_continente(session, cont))

        resultados = await asyncio.gather(*tasks)
        filas = [r for r in resultados if r is not None]

    print("  > Consultas finalizadas.\n")

    async with aiohttp.ClientSession() as session:
        data_total = await fetch_json(session, "https://resultadoelectoral.onpe.gob.pe/presentacion-backend/resumen-general/totales?idEleccion=10&tipoFiltro=eleccion")

        if not data_total or "data" not in data_total:
            print("  Error obteniendo total nacional")
            porcentaje_nacional = 0
        else:
            porcentaje_nacional = data_total["data"]["actasContabilizadas"]

    print(" " * 51 + "|" + f"Votos al {porcentaje_nacional:.3f}%".center(21) + "|" + "Proyección al 100%".center(21))
    print(" ".ljust(4) + "Localidad".ljust(36) + "Contado".rjust(10) + " |" + "López".rjust(10) + "Sánchez".rjust(10) + " |" + "López".rjust(10) + "Sánchez".rjust(10))
    print("  " + "-" * 94)

    tot_l_cont = tot_s_cont = 0
    tot_l_proy = tot_s_proy = 0
    for row in filas:
        ubicacion = str(row["ubicacion"])
        if len(ubicacion) > 38:
            ubicacion = ubicacion[:35] + "..."
        ubicacion = ubicacion.ljust(38)
        actas_str = f"{row['actas']:.3f}%".rjust(9)
        v = row["votos"]
        p = row["proy"]
        cont = [f"{int(v['Lopez']):>10}", f"{int(v['Sanchez']):>10}"]
        proy = [f"{int(p['Lopez']):>10}", f"{int(p['Sanchez']):>10}"]
        print("  " + f"  {str(row['ubicacion'])[:36].ljust(36)} {actas_str} |{''.join(cont)} |{''.join(proy)}")
        tot_l_cont += v["Lopez"]
        tot_s_cont += v["Sanchez"]
        tot_l_proy += p["Lopez"]
        tot_s_proy += p["Sanchez"]

    print("  " + "-" * 94)
    linea_cont = f"{int(tot_l_cont):>9}{int(tot_s_cont):>10}"
    linea_proy = f"{int(tot_l_proy):>10}{int(tot_s_proy):>10}"

    print(" " * 51 + "|" + "Votos contados".center(21) + "|" + "Votos proyectados".center(23))
    print(" " * 51 + "|"  + "López".rjust(10) + "Sánchez".rjust(10) +  " |" + "López".rjust(10) + "Sánchez".rjust(10))
    print(" " * 51 + f"| {linea_cont} |{linea_proy}")

    print("\n\n  La proyección asume que la distribución de votos se mantiene en las actas pendientes de cada localidad.")
    print("  Hipótesis más confiable a mayor porcentaje de actas contabilizadas.\n")

if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    asyncio.run(main())
    input("\n  Presiona ENTER para cerrar...\n\n  ")