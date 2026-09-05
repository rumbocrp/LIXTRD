# ADR-002 — Piloto separado, integración futura en Trading Journal

**Estado:** aceptada como dirección por decisión del dueño  
**Fecha:** 2026-08-30  
**Reemplaza:** ADR-001 para topología, UI e integración

## Contexto

Trading Journal está construido y no se debe modificar durante el piloto. SistemaLuces debe
probarse con cuentas demo y operativas simuladas, pero su diseño anterior produjo una UI y
un stack de presentación divergentes. El dueño quiere que el Sistema de Luces pueda vivir
dentro del Journal en el futuro.

Compartir hoy la base o editar el Journal aumenta el riesgo. Mantener también una UI Python
sin el sistema visual del Journal aumenta el costo de integración futura.

## Decisión

1. SistemaLuces permanece en un repositorio, proceso de motor y base independientes durante
   el piloto.
2. El motor sigue en Python y expone una Proyección de lectura versionada sólo por loopback.
3. La interfaz piloto se construye con el stack y contrato visual compatibles con Trading
   Journal, en una aplicación standalone.
4. La futura integración traslada el módulo visual a `/luces` dentro del layout del Journal y
   consume el motor mediante un BFF/Route Handler read-only.
5. No se comparte `tj.db`, no se importa runtime del Journal y no se usa iframe.
6. Trading Journal permanece de solo lectura en todas las fases R0–R7.

## Motivos

- Permite probar y descartar el motor sin comprometer el Journal.
- Reutiliza desde ahora la arquitectura de información, accesibilidad, tokens y stack que el
  operador ya conoce.
- Mantiene un seam único: Proyección de lectura.
- Evita duplicar reglas financieras en TypeScript y Python.
- Hace que una ausencia del motor aparezca como estado de datos, no como caída del Journal.

## Alternativas rechazadas

### Integrar directamente en Trading Journal ahora

Rechazada por `DO-01`: toca un producto terminado antes de validar el motor.

### Mantener UI Python definitiva

Rechazada: perpetúa dos sistemas visuales y obliga a reescribir la presentación al integrar.

### Compartir SQLite

Rechazada: mezcla migraciones, permisos, backups y ciclos de vida. La unión futura ocurre en
la presentación/contrato, no en las tablas.

### Iframe dentro del Journal

Rechazada: duplica navegación, tema, accesibilidad, CSP y manejo de errores; no es una
integración de producto.

### Reescribir el motor en TypeScript

Fuera de alcance. Sólo se reconsidera tras demostrar que el sidecar crea un costo medido y
material.

## Consecuencias

- Habrá dos procesos locales durante el piloto: panel y motor.
- Se añade un contrato HTTP y consumer tests.
- El panel standalone debe mantener compatibilidad con versiones del Journal.
- La futura incorporación requiere trabajo en el Journal, pero queda acotado a UI/BFF,
  navegación, textos, operación y pruebas de host.
- Una decisión posterior puede fusionar procesos o datos, pero necesita ADR y migración.

## Verificación

ADR-002 se considera implementada cuando `G-R5` prueba la UI standalone compatible y `G-R7`
prueba el host fixture de `/luces` sin tocar el repositorio Trading Journal.

