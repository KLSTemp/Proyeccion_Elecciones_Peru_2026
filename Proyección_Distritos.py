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

total_tasks = 0
done_tasks = 0
progress_lock = asyncio.Lock()

def progreso(msg):
    width = shutil.get_terminal_size().columns
    msg = msg[:width - 1]
    sys.stdout.write("\r" + " " * width)
    sys.stdout.write("\r" + msg)
    sys.stdout.flush()

async def marcar_progreso(texto_extra=""):
    global done_tasks, total_tasks
    async with progress_lock:
        done_tasks += 1
        porcentaje = (done_tasks / total_tasks) * 100 if total_tasks else 0
        progreso(f"  > Progreso: [{porcentaje:5.1f}%] ")

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
                    except Exception as e:
                        text = await resp.text()
                        print(f"\n  Error parseando JSON en {url}: {e}")
                        if text.strip().startswith(('{', '[')):
                            return json.loads(text)
        except Exception as e:
            if intento == retries - 1:
                print(f"\n  Error final en fetch:\n  URL: {url}\n  Error: {repr(e)}")
                return None
        await asyncio.sleep(0.6 * (intento + 1))
    return None

async def wrap_task(coro, descripcion):
    try:
        result = await coro
        await marcar_progreso(descripcion)
        return result
    except Exception as e:
        print(f"\n  Error en tarea [{descripcion}]: {repr(e)}")
        await marcar_progreso(f"ERROR {descripcion}")
        return None

async def procesar_distrito(session, dep_nombre, dep_ubigeo, prov_ubigeo, prov_nombre, dist):
    dist_nombre = dist["nombre"]
    dist_ubigeo = dist["ubigeo"]

    try:
        url_cand = (
            "https://resultadoelectoral.onpe.gob.pe/presentacion-backend/"
            f"eleccion-presidencial/participantes-ubicacion-geografica-nombre?"
            f"tipoFiltro=ubigeo_nivel_03&idAmbitoGeografico=1&ubigeoNivel1={dep_ubigeo}"
            f"&ubigeoNivel2={prov_ubigeo}&ubigeoNivel3={dist_ubigeo}&idEleccion=10"
        )

        url_actas = (
            "https://resultadoelectoral.onpe.gob.pe/presentacion-backend/"
            f"resumen-general/totales?idAmbitoGeografico=1&idEleccion=10"
            f"&tipoFiltro=ubigeo_nivel_03&idUbigeoDepartamento={dep_ubigeo}"
            f"&idUbigeoProvincia={prov_ubigeo}&idUbigeoDistrito={dist_ubigeo}"
        )

        data_cand, data_actas = await asyncio.gather(
            fetch_json(session, url_cand),
            fetch_json(session, url_actas)
        )

        if not data_cand or not data_actas:
            return None

        actas = float(data_actas["data"]["actasContabilizadas"])
        votos = obtener_votos(data_cand)

        proy = {k: round(v / actas * 100) if actas > 0 else 0 for k, v in votos.items()}

        return {
            "ubicacion": f"{dep_nombre} - {prov_nombre} - {dist_nombre}",
            "actas": actas,
            "votos": votos,
            "proy": proy
        }

    except Exception as e:
        print(f"\n  Error distrito [{dist_nombre}]\n  {repr(e)}")
        return None

async def procesar_pais(session, cont):
    cont_nombre = cont["nombre"]
    cont_ubigeo = cont["ubigeo"]

    try:
        url_paises = (
            "https://resultadoelectoral.onpe.gob.pe/presentacion-backend/ubigeos/provincias?"
            f"idEleccion=10&idAmbitoGeografico=2&idUbigeoDepartamento={cont_ubigeo}"
        )

        data_paises = await fetch_json(session, url_paises)

        if not data_paises or "data" not in data_paises:
            return None

        resultados = []

        for pais in data_paises["data"]:
            pais_nombre = pais["nombre"]
            pais_ubigeo = pais["ubigeo"]

            url_cand = (
                "https://resultadoelectoral.onpe.gob.pe/presentacion-backend/"
                f"eleccion-presidencial/participantes-ubicacion-geografica-nombre?"
                f"tipoFiltro=ubigeo_nivel_02&idAmbitoGeografico=2"
                f"&ubigeoNivel1={cont_ubigeo}&ubigeoNivel2={pais_ubigeo}&idEleccion=10"
            )

            url_actas = (
                "https://resultadoelectoral.onpe.gob.pe/presentacion-backend/"
                f"resumen-general/totales?idAmbitoGeografico=2&idEleccion=10"
                f"&tipoFiltro=ubigeo_nivel_02"
                f"&idUbigeoDepartamento={cont_ubigeo}"
                f"&idUbigeoProvincia={pais_ubigeo}"
            )

            data_cand, data_actas = await asyncio.gather(
                fetch_json(session, url_cand),
                fetch_json(session, url_actas)
            )

            if not data_cand or not data_actas:
                continue

            actas = float(data_actas["data"]["actasContabilizadas"])
            votos = obtener_votos(data_cand)

            proy = {k: round(v / actas * 100) if actas > 0 else 0 for k, v in votos.items()}

            resultados.append({
                "ubicacion": f"Extranjero - {cont_nombre} - {pais_nombre}",
                "actas": actas,
                "votos": votos,
                "proy": proy
            })

        return resultados

    except Exception as e:
        print(f"\n  Error país [{cont_nombre}]\n  {repr(e)}")
        return None

async def main():
    global total_tasks, done_tasks

    async with aiohttp.ClientSession() as session:

        data_dep = await fetch_json(
            session,
            "https://resultadoelectoral.onpe.gob.pe/presentacion-backend/ubigeos/departamentos?idEleccion=10&idAmbitoGeografico=1"
        )

        departamentos = {d["nombre"]: d["ubigeo"] for d in data_dep["data"]}

        provincias_cache = {}
        distritos_cache = {}

        tasks_prov = [
            fetch_json(
                session,
                f"https://resultadoelectoral.onpe.gob.pe/presentacion-backend/ubigeos/provincias?"
                f"idEleccion=10&idAmbitoGeografico=1&idUbigeoDepartamento={ubigeo}"
            )
            for ubigeo in departamentos.values()
        ]

        prov_results = await asyncio.gather(*tasks_prov)

        for (dep_nombre, dep_ubigeo), data in zip(departamentos.items(), prov_results):
            provincias_cache[dep_ubigeo] = data["data"] if data and "data" in data else []

        tasks_dist = []

        for dep_nombre, dep_ubigeo in departamentos.items():
            for prov in provincias_cache[dep_ubigeo]:

                prov_ubigeo = prov["ubigeo"]

                dist_data = await fetch_json(
                    session,
                    f"https://resultadoelectoral.onpe.gob.pe/presentacion-backend/ubigeos/distritos?"
                    f"idEleccion=10&idAmbitoGeografico=1&idUbigeoProvincia={prov_ubigeo}"
                )

                distritos_cache[(dep_ubigeo, prov_ubigeo)] = dist_data["data"] if dist_data and "data" in dist_data else []

                for dist in distritos_cache[(dep_ubigeo, prov_ubigeo)]:
                    tasks_dist.append(
                        wrap_task(
                            procesar_distrito(session, dep_nombre, dep_ubigeo, prov_ubigeo, prov["nombre"], dist),
                            f"Distrito {dist['nombre']}"
                        )
                    )

        data_cont = await fetch_json(
            session,
            "https://resultadoelectoral.onpe.gob.pe/presentacion-backend/ubigeos/departamentos?idEleccion=10&idAmbitoGeografico=2"
        )

        continentes = data_cont.get("data", [])

        tasks_paises = [
            wrap_task(procesar_pais(session, cont), f"Pais {cont['nombre']}")
            for cont in continentes
        ]

        total_tasks = len(tasks_dist) + len(tasks_paises)
        done_tasks = 0

        timestamp = datetime.now().strftime('%d/%m/%y %I:%M %p')
        print(f"\n  > Consultando 'https://resultadoelectoral.onpe.gob.pe/' ({timestamp}).\n")

        resultados_distritos, resultados_paises = await asyncio.gather(
            asyncio.gather(*tasks_dist),
            asyncio.gather(*tasks_paises)
        )

        filas = []

        for r in resultados_distritos:
            if r:
                filas.append(r)

        for grupo in resultados_paises:
            if grupo:
                filas.extend(grupo)

    async with aiohttp.ClientSession() as session:
        data_total = await fetch_json(
            session,
            "https://resultadoelectoral.onpe.gob.pe/presentacion-backend/resumen-general/totales?idEleccion=10&tipoFiltro=eleccion"
        )

        porcentaje_nacional = data_total["data"]["actasContabilizadas"] if data_total and "data" in data_total else 0

    print("\n\n" + " " * 75 + "|" + f"Votos al {porcentaje_nacional:.3f}%".center(21) + "|" + "Proyección al 100%".center(21))
    print("    " + "Localidad".ljust(60) + "Contado".rjust(10) + " |" + "Lopez".rjust(10) + "Sanchez".rjust(10) + " |" + "Lopez".rjust(10) + "Sanchez".rjust(10))
    print("  " + "-" * 118)

    tot_l_cont = tot_s_cont = 0
    tot_l_proy = tot_s_proy = 0

    for row in filas:
        ubicacion = " - ".join([p.title() for p in str(row["ubicacion"]).split(" - ")])
        if len(ubicacion) > 60:
            ubicacion = ubicacion[:57] + "..."
            print("\n\n\n")
        ubicacion = ubicacion.ljust(60)

        actas_str = f"{row['actas']:.3f}%".rjust(9)

        v = row["votos"]
        p = row["proy"]

        cont = f"{int(v['Lopez']):>10}{int(v['Sanchez']):>10}"
        proy = f"{int(p['Lopez']):>10}{int(p['Sanchez']):>10}"

        print(f"    {ubicacion} {actas_str} |{cont} |{proy}")

        tot_l_cont += v["Lopez"]
        tot_s_cont += v["Sanchez"]
        tot_l_proy += p["Lopez"]
        tot_s_proy += p["Sanchez"]

    print("  " + "-" * 118)
    print(" " * 75 + "|" + "Votos contados".center(21) + "|" + "Votos proyectados".center(23))
    print(" " * 75 + "|" + "Lopez".rjust(10) + "Sanchez".rjust(10) + " |" + "Lopez".rjust(10) + "Sanchez".rjust(10))
    print(" " * 75 + f"| {f"{int(tot_l_cont):>9}{int(tot_s_cont):>10}"} |{f"{int(tot_l_proy):>10}{int(tot_s_proy):>10}"}")
    print("\n\n  La proyección asume que la distribución de votos se mantiene en las actas pendientes de cada localidad.")
    print("  Hipótesis más confiable a mayor porcentaje de actas contabilizadas.\n")

if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    asyncio.run(main())
    input("\n  Presiona ENTER para salir...\n\n  ")