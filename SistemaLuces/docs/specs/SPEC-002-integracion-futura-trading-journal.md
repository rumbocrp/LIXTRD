# SPEC-002 — Sistema de Luces preparado para Trading Journal

**Estado:** APROBADA COMO BASE DOCUMENTAL por instrucción del dueño  
**Versión:** 2.1.0  
**Fecha:** 2026-08-30  
**Reemplaza:** SPEC-001  
**Implementación:** bloqueada hasta cerrar las Puertas del plan

## Problem Statement

El dueño necesita probar un Sistema de Luces independiente que observe US500 y permita
monitorear operativas simuladas asociadas a cuentas demo. El producto visible, la
documentación y los gates actuales no representan esa necesidad: mezclan contratos útiles
con un simulador multi-activo histórico, muestran cifras prefijadas como rendimiento y
declaran terminada una integración que no existe.

Trading Journal ya está construido y no debe modificarse durante el piloto. Sin embargo, la
experiencia y la arquitectura de SistemaLuces deben evitar una segunda migración: en el
futuro la función de luces debe poder aparecer dentro del shell del Journal como una ruta
propia, sin compartir bases ni reescribir el motor.

## Solution

Construir el piloto como dos adaptadores alrededor de un único motor:

1. motor Python independiente con datos, modelos, simulación y auditoría propios;
2. interfaz del mismo stack y sistema visual de Trading Journal;
3. Proyección de lectura versionada como único seam entre ambos;
4. fuente cTrader/Pepperstone de cuenta demo en modo read-only, sujeta a validación real;
5. replay y shadow por la misma ruta que alimenta la interfaz;
6. amarillo/`MONITORIZAR` y `NO_DATA` como estados seguros;
7. cero capacidad de órdenes y cero acceso a `tj.db`;
8. futura incorporación de la interfaz como `/luces` dentro del Journal, conservando el
   motor como servicio local hasta una decisión posterior.
9. fuente pública transitoria Yahoo Finance en `SHADOW` con allowlist `^GSPC`, `TSLA`,
   `AAPL` y `GC=F`, para probar el monitor 24/7 sin presentarla como broker, cuenta demo o
   precio ejecutable;
10. diagnóstico independiente por activo: cada fila reserva luz/barra/umbrales propios y
    permanece N/A hasta recibir evidencia verificable de su fórmula o modelo.

## User Stories

1. Como operador, quiero distinguir si veo datos sintéticos, replay, shadow o demo observada, para no confundir una prueba con el mercado.
2. Como operador, quiero ver verde/largo, amarillo/monitorizar o rojo/corto con texto, para no depender sólo del color.
3. Como operador, quiero conocer la edad y el último corte de mercado, para saber si la luz sigue vigente.
4. Como operador, quiero ver razones concretas de cada luz, para poder decidir con criterio propio.
5. Como operador, quiero ver la salud de la fuente y del modelo, para abstenerme cuando el sistema perdió validez.
6. Como operador, quiero revisar el historial de transiciones, para entender cómo cambió la lectura durante la sesión.
7. Como operador, quiero que una caída, hueco o dato obsoleto fuerce amarillo, para no recibir una señal sobre información degradada.
8. Como operador, quiero observar operativas simuladas sin que el sistema envíe órdenes, para probarlo sin riesgo de ejecución.
9. Como operador, quiero comparar una simulación con Ejecuciones leídas de una cuenta demo, para medir diferencias de entrada, salida y costos.
10. Como operador, quiero que una Ejecución no conciliada permanezca visible, para evitar sesgo por omitir decisiones manuales.
11. Como operador, quiero que P&L y riesgo aparezcan como N/A cuando falte el contrato económico, para no ver dinero inventado.
12. Como operador, quiero que toda métrica declare periodo, muestra, fuente y versión, para interpretar su alcance.
13. Como operador, quiero que el producto use la misma estructura visual que Trading Journal, para aprender una sola interfaz.
14. Como operador, quiero usarlo en escritorio y móvil con los mismos estados accesibles, para supervisarlo desde mis dispositivos.
15. Como operador, quiero que el módulo futuro aparezca dentro del Journal sin iframe ni segundo diseño, para conservar una experiencia coherente.
16. Como dueño, quiero mantener Trading Journal intacto durante el piloto, para no poner en riesgo un producto ya terminado.
17. Como dueño, quiero que SistemaLuces tenga base, backups y releases propios, para poder descartarlo o evolucionarlo sin tocar el Journal.
18. Como dueño, quiero aprobar manualmente la promoción de modelos, para que una métrica aislada no cambie el comportamiento operativo.
19. Como dueño, quiero conservar baseline, logística y boosting como candidatos comparables, para saber si la complejidad realmente aporta valor.
20. Como dueño, quiero que resultados extraordinarios disparen una revisión de fuga, para no aceptar evidencia demasiado buena para ser cierta.
21. Como auditor, quiero reconstruir una decisión desde eventos, versiones y hashes, para verificar qué se sabía en ese momento.
22. Como auditor, quiero que datos ausentes sigan ausentes, para detectar huecos en lugar de recibir ceros o defaults.
23. Como auditor, quiero que las Puertas separen contratos, integración, fuente, modelos, UI y shadow, para que un PASS unitario no certifique el producto.
24. Como desarrollador, quiero un único pipeline para replay, shadow y UI, para evitar dos motores con resultados diferentes.
25. Como desarrollador, quiero una frontera de lectura estable, para cambiar la UI sin reescribir el motor.
26. Como desarrollador, quiero reutilizar tokens y componentes por contrato versionado, para evitar copiar estilos que luego diverjan.
27. Como desarrollador, quiero mantener el dominio independiente de Next, SQLite y cTrader, para probarlo y reemplazar adaptadores.
28. Como futuro integrador, quiero mover el módulo visual a una route group del Journal, para heredar su layout sin cambiar la URL pública.
29. Como futuro integrador, quiero consultar el motor desde el servidor del Journal, para mantener el navegador en el mismo origen y el motor en loopback.
30. Como responsable de seguridad, quiero que no exista clase, endpoint, scope o comando de órdenes, para que el piloto no pueda operar accidentalmente.
31. Como operador, quiero ver SP500, TSLA, AAPL y oro en la misma pantalla, para comparar sus cortes sin cambiar de proceso ni perder contexto.
32. Como operador, quiero que cada uno pueda tener su propio diagnóstico, para que una señal de TSLA, AAPL u oro no se confunda con la del SP500.

## Implementation Decisions

- El piloto usa US500 como Instrumento canónico y `America/New_York` como zona del Día
  operativo.
- La entrada es event-driven; las decisiones publicables se cierran a 30 y 60 segundos.
- El motor permanece en Python con dominio puro, adaptadores de fuente, persistencia SQLite,
  laboratorio de modelos, política, simulación y Proyección de lectura.
- La interfaz piloto usa las versiones compatibles con Trading Journal de Next.js App
  Router, React, TypeScript y Tailwind. No contiene reglas financieras.
- El sistema visual se obtiene de un snapshot versionado de tokens semánticos y de
  componentes; no importa paquetes del Journal ni copia colores manualmente.
- La futura integración añade una ruta `/luces` dentro del layout existente del Journal. La
  route group organiza el módulo sin alterar la URL ni duplicar el root layout.
- El servidor de interfaz consulta el motor por loopback. Para datos cambiantes usa lectura
  sin caché; un Route Handler/BFF sólo expone contratos de lectura al navegador.
- La Proyección de lectura incluye estado de procedencia, luz+palabra, corte, edad, salud,
  razones, modelo/política, transiciones, simulaciones y métricas con linaje.
- La fuente demo debe demostrar cuenta demo y capacidades read-only antes de abrir stream.
  Fixtures y mensajes inyectados viven en un adaptador distinto con estado `SINTETICO`.
- Yahoo Finance se encapsula en adaptadores reemplazables: WebSocket se suscribe a la
  allowlist `^GSPC`, `TSLA`, `AAPL`, `GC=F` y REST recupera snapshots en paralelo. La
  Proyección declara una colección `market_assets` con timestamps, transporte, estado,
  antigüedad y demora por símbolo; nunca sintetiza bid/ask, OFI u order flow.
- `GC=F` se presenta como futuro continuo de oro Yahoo/COMEX, nunca como XAU/USD spot.
- Cada elemento de `market_assets` admite un `diagnostico_semaforo` opcional e independiente;
  un precio sin fórmula/modelo validado conserva ese diagnóstico en N/A.
- La UI no accede a tablas ni al event store; sólo consume Proyecciones de lectura.
- Trading Journal no se modifica, no se abre `tj.db` y no se comparte migración.
- Profundidad, OFI y microprecio permanecen ausentes hasta superar una Puerta con cinco
  sesiones de evidencia real.
- Baseline/siempre amarillo, regresión logística calibrada y boosting tabular se evalúan con
  ventanas temporales purgadas, costos y artefactos versionados.
- El Modelo campeón requiere Puerta y aprobación humana. Falta de campeón fuerza amarillo.
- Los estados de exposición válidos son `NO_DATA`, `SINTETICO`, `REPLAY`, `SHADOW` y
  `DEMO_OBSERVADO`. `REAL` queda fuera de esta SPEC.

## Testing Decisions

- El seam principal es la Proyección de lectura. El test de mayor nivel inyecta un archivo
  de Eventos de mercado por el puerto de replay y verifica la proyección completa producida
  por el mismo composition root usado en shadow.
- Los tests validan comportamiento observable, no nombres internos de clases ni conteos de
  líneas.
- Los adaptadores replay, sintético y cTrader demo comparten un contrato, pero cTrader tiene
  una suite de integración separada que exige handshake/stream real o queda `BLOCKED`.
- La integración Yahoo tiene una prueba externa opt-in sobre los cuatro símbolos. Su PASS
  prueba precios, metadata, seam público y UI, no la cuenta demo, economía, profundidad ni
  `G-R3`.
- Persistencia se prueba con SQLite real temporal, reinicio de proceso, integridad y restore.
- Causalidad se prueba añadiendo eventos futuros y verificando que decisiones pasadas no
  cambian.
- Modelos se prueban con fixtures dorados y evaluación walk-forward; la Puerta de modelo
  exige dataset/artefacto/manifiesto, no sólo unit tests.
- UI se prueba en los dos temas, teclado, 320 px, escritorio, estados vacíos/obsoletos/error,
  contraste AA y ausencia de afirmaciones sin linaje.
- Seguridad escanea runtime, scripts, dependencias y contratos para demostrar ausencia de
  capacidad de órdenes y exposición fuera de loopback.
- La futura integración se prueba sin tocar el Journal: un host fixture monta el módulo en
  `/luces` con el contrato de layout y BFF esperados.

## Out of Scope

- modificar cualquier archivo, base, migración o proceso de Trading Journal durante el
  piloto;
- enviar, modificar, cancelar o cerrar órdenes, incluso en demo;
- observar o aceptar cuentas live;
- compartir `tj.db`, `luces.db`, procesos de migración o paquetes de dominio;
- prometer rentabilidad, accuracy mínima, Sharpe o drawdown sin evidencia versionada;
- usar OFI/L2/microprecio sintéticos en la ruta operativa;
- entrenar con datos personales del Journal sin una autorización contractual posterior;
- nube, multiusuario, autenticación remota o acceso fuera de loopback;
- usar Yahoo como sustituto de la Fuente demo, como precio ejecutable o como evidencia de
  order flow/latencia del broker;
- fusionar el motor Python dentro del runtime Node del Journal.

## Further Notes

La interfaz del primer intento y el motor `quant` pueden conservarse sólo como laboratorio
histórico rotulado `SINTETICO`. No son una versión reducida del producto operativo. La primera
entrega útil de esta SPEC es una pantalla honesta en `NO_DATA` conectada al composition root,
no una pantalla llena de valores de ejemplo.
