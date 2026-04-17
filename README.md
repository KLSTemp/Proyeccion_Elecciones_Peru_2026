# Proyeccion_Elecciones_Peru_2026
Script simple en Python que obtiene datos en tiempo real desde la web de la ONPE y proyecta resultados presidenciales.

## Cómo funciona
- Consulta los endpoints públicos de la [ONPE](https://resultadoelectoral.onpe.gob.pe/)
- Obtiene votos por candidato y porcentaje de actas
- Proyecta los resultados al 100% mediante escalamiento

## Metodología
Se aplica una regla directa:  
`votos_proyectados = votos_actuales / %_de_actas_contabilizadas`  
- La proyección asume que la distribución de votos observada se mantiene en las actas pendientes.  
- La hipótesis es mas confiable a mayor porcentaje de actas contabilizadas y a mayor nivel de desagregación geográfica.  
- Se puede ejecutar a nivel de regiones o provincias.

## Descarga
- Proyección_Regiones.exe  
- Proyección_Provincias.exe
