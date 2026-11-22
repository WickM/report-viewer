# Report Templates

Vorlagen für wiederkehrende Berichte. Jede Vorlage ist eine Markdown-Datei mit Platzhaltern in `[eckigen Klammern]`. Beim Publish mit `source_path` die Platzhalter ersetzen, Rest bleibt.

## Vorlagen

| Vorlage | Wann | Format |
|---------|------|--------|
| `weekly-status.md` | Wöchentlicher Statusbericht (Mo-Fr, Ampel, Top-3) | `md` |
| `research-summary.md` | Recherche-Zusammenfassung (These, Evidenz, Contra, Fazit) | `md` |
| `architecture-decision.md` | Architektur-Entscheidung (ADR-Format: Kontext, Entscheidung, Konsequenzen) | `md` |

## Eigene Vorlage

Siehe `CUSTOM.md` — 5 Schritte zur eigenen Vorlage.

## Verwendung

1. Vorlage aus `references/` kopieren
2. Platzhalter `[...]` ersetzen
3. Als `.md`-Datei speichern (z.B. im Brain-Vault unter `03_Projects/` oder `brain/research/`)
4. Mit `source_path` publizieren:
   ```bash
   curl -s -X POST http://localhost:8765/api/publish \
     -H "Content-Type: application/json" \
     -d '{"title":"[Titel]","format":"md","source_path":"/pfad/zur/datei.md"}'
   ```
