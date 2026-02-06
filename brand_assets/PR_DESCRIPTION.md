# PR Description Template for home-assistant/brands

## Title
Add energa_mobile brand (official Energa | GRUPA ORLEN branding)

## Description

```markdown
Adding brand assets for `energa_mobile` custom integration.

**Domain:** `energa_mobile`
**Repository:** https://github.com/ergo5/hass-energa-my-meter-api

## Logo Source

This is the **official Energa Obrót** logo from the ORLEN Group branding guidelines.

**Source:** [Energa Press Office](https://energa.pl) - "Logo | Zdjęcia" section in the media kit.

The logo includes:
- Official Energa "e" symbol
- "Energa | GRUPA ORLEN" text (current corporate branding since ORLEN acquisition)
- "Obrót" designation (Energa Obrót Sp. z o.o. - the retail energy company)

## Reference to Previous PR

This replaces the reverted PR #8819 which used non-official branding.
Per @klaasnicolaas and @frenck feedback, this submission uses the correct manufacturer branding.

## Files Added

- `custom_integrations/energa_mobile/icon.png` (256x256)
- `custom_integrations/energa_mobile/icon@2x.png` (512x512)  
- `custom_integrations/energa_mobile/logo.png` (horizontal logo)
```

## Key Points to Emphasize

1. **"GRUPA ORLEN"** - Energa is now part of ORLEN Group, so the official logo includes this
2. **"Obrót"** - This is the specific Energa company (energy retail), not Energa Operator (grid)
3. **Reference PR #8819** - Shows you fixed the issue they pointed out
