# Eigene Report-Vorlage erstellen

5 Schritte, um eine neue Vorlage für wiederkehrende Berichte anzulegen.

## Schritt 1: Vorlage kopieren

```bash
cp references/weekly-status.md references/[mein-bericht].md
```

Oder eine bestehende Vorlage als Basis nehmen und anpassen.

## Schritt 2: Platzhalter definieren

Ersetze alle `[eckigen Klammern]` durch konkrete Platzhalter, die zu deinem Bericht passen. Faustregel:

- **Inhalt** = `[was hier steht]`
- **Struktur** = `[wie viele Punkte / Zeilen]`
- **Format** = `[Ampel, Datum, URL, etc.]`

Beispiel:
```markdown
# [Projekt] — [Berichtstyp]
**Zeitraum:** [KW XX]
**Status:** [🟢🟡🔴]
```

## Schritt 3: In README eintragen

Füge einen Eintrag in `references/README.md` hinzu:

```markdown
| [mein-bericht].md | [Wann verwenden?] | [Format: md/html/excalidraw] |
```

## Schritt 4: Testen

Erstelle einen Test-Bericht mit der neuen Vorlage:

```bash
curl -s -X POST http://localhost:8765/api/publish \
  -H "Content-Type: application/json" \
  -d '{"title":"Test [mein-bericht]","format":"md","content":"# Test\n\n[Platzhalter]-Beispiel"}'
```

Prüfe im Browser, ob:
- alle Platzhalter sinnvoll sind
- das Layout (Mermaid, KaTeX, Tabellen) korrekt rendert
- die Kommentarfunktion funktioniert

## Schritt 5: Committen

```bash
git add references/[mein-bericht].md references/README.md
git commit -m "feat: add [mein-bericht] template"
git push
```

Fertig. Die Vorlage ist jetzt für alle Agenten verfügbar, die den report-viewer-Skill nutzen.

## Tipps

- **Wiederverwendbarkeit:** Halte Platzhalter generisch (`[Projekt]` statt `[FooBar]`) damit die Vorlage für mehrere Projekte funktioniert.
- **Versionierung:** Wenn du eine Vorlage grundlegend änderst, committe das als Breaking Change und erhöhe die Skill-Version.
- **Beispiele:**siehe `weekly-status.md`, `research-summary.md`, `architecture-decision.md`
