# Seguridad de la cadena de herramientas del frontend

Node y npm son solo herramientas de desarrollo y compilación: el resultado es un paquete de
ficheros estáticos que sirve Python. **Ni la aplicación en producción ni el backend ejecutan
Node**, así que las vulnerabilidades de Node afectan a la máquina de desarrollo, no a quien usa
la aplicación.

## Medidas en el repositorio

| Medida | Dónde | Efecto |
|---|---|---|
| Versión mínima de Node | `engines` de `package.json` + `engine-strict=true` en `.npmrc` | npm rechaza instalar con una versión vulnerable (`EBADENGINE`). |
| Sin scripts de instalación | `ignore-scripts=true` | Una dependencia comprometida no ejecuta código al instalarse. Solo `fsevents` (módulo nativo opcional de macOS) tenía uno. |
| Versiones exactas | `save-exact=true` y 28 dependencias directas fijadas | Una instalación sin lockfile no recoge una versión nueva y maliciosa. |
| Instalación reproducible | `npm ci` (nunca `npm install` para instalar) | Usa el lockfile y comprueba el hash `sha512` de cada paquete. |
| Auditoría | `npm audit --audit-level=high` y `npm audit signatures` | Avisos conocidos y firmas del registro. |
| Dependencias mínimas | 6 de ejecución | Menos superficie: el i18n es propio y mínimo en lugar de una librería. |
| Servidor de desarrollo local | `host: 127.0.0.1` | No se expone a la red. |

## Incidentes revisados (noviembre de 2026)

- **Node.js, versiones de seguridad del 21 de octubre de 2026.** Ocho CVE afectan a la rama 24,
  cuatro de gravedad alta: escritura fuera de límites en el decodificador Brotli con posible
  ejecución remota, y evasión de la comprobación de nombre de host en TLS. Corregidas en
  **24.22.1** (22.23.4 y 26.12.1 en sus ramas). Fuente:
  [Node.js, Security Releases](https://nodejs.org/en/blog/vulnerability/october-2026-security-releases).
  Por eso el mínimo de `engines` es `^22.23.4 || ^24.22.1 || >=26.12.1`.
- **Ataque a `keyv` y paquetes relacionados (agosto de 2026, familia Shai-Hulud).** Versiones
  comprometidas: `keyv` 6.0.0, `flat-cache` 6.1.24, `file-entry-cache` 11.1.6, entre otras.
  Fuentes: [CSA Singapur](https://csa.gov.sg/alerts-and-advisories/advisories/ad-2026-009) y
  [Chainguard](https://www.chainguard.dev/unchained/the-keyv-and-cacheable-npm-supply-chain-attack-inside-the-mini-shai-hulud-campaign).
  El árbol contiene `keyv` 4.5.4, `flat-cache` 4.0.1 y `file-entry-cache` 8.0.0, publicadas en
  2023–2024: **no afectadas**.

Comprobaciones realizadas: ninguna versión afectada en el lockfile, 434 entradas con `sha512`
y desde `registry.npmjs.org`, 388 paquetes instalados con firma de registro verificada
(`npm audit signatures`) y sin artefactos de persistencia de la campaña en el repositorio.
Estas comprobaciones no detectan un compromiso publicado hace pocas horas.

## Riesgo aceptado

`npm audit` informa una incidencia **moderada** (`minimatch`, denegación de servicio por
patrones glob, GHSA-g3hv-75wg-m249) propagada por la cadena de ESLint. Solo afecta a la
herramienta de lint con patrones propios y no llega al paquete compilado. La corrección que
sugiere npm (`--force`) degrada `eslint-plugin-jsx-a11y` de forma incompatible, así que se
mantiene hasta que ESLint actualice su dependencia.

## Al añadir o actualizar dependencias

1. Usar Node dentro de `engines` y `npm install --save-exact <paquete>`.
2. Revisar el diff de `package-lock.json`: paquetes nuevos, `resolved` fuera de
   `registry.npmjs.org` y entradas con `hasInstallScript`.
3. Ejecutar `npm audit signatures` y `npm audit --audit-level=high`.
4. Preferir la biblioteca estándar o código propio pequeño antes que una dependencia nueva.
5. Si una dependencia necesita scripts de instalación, justificarlo y no desactivar
   `ignore-scripts` para todo el proyecto.
