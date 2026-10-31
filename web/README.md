# Front-end (Next.js + Leaflet)

```bash
npx create-next-app@latest . --ts --app --eslint
npm i leaflet react-leaflet
npm i -D @types/leaflet
```

## Estrutura sugerida

```
web/
  public/data/            # summary, municipios, series, windows, health (gerados pelo pipeline)
  src/app/page.tsx        # layout: mapa + painel
  src/components/Map.tsx  # react-leaflet; importe com next/dynamic({ ssr: false })
  src/components/Timeline.tsx   # série diária com marcadores em 04/10 e 25/10
  src/components/WindowCompare.tsx  # antes × depois de cada turno, lado a lado
  src/components/Filters.tsx    # período, tipo de violência, natureza do relato
  src/components/Health.tsx     # painel de saúde do pipeline e F1 do teste de deriva
  src/lib/data.ts         # tipos TS do contrato + fetch dos JSON
  src/app/print.css       # @media print para exportar PDF do dashboard
```

## Pontos de atenção

- Leaflet usa `window`: o componente do mapa deve ser client-only (`ssr: false`).
- Ícones padrão do Leaflet quebram no bundler; use `L.circleMarker` (bolhas) e evite ícones de imagem.
- Raio da bolha proporcional a `sqrt(total)` (área ∝ volume), com legenda.
- Os marcadores e os períodos vêm de `windows.json`; não escreva datas no front.
- Mostre sempre o `n` de cada janela e "X% dos itens foram geolocalizados", com link para a metodologia.
- Mostre taxa (não só contagem) na comparação antes/depois, com a incerteza.
- Tiles: OpenStreetMap com atribuição visível, respeitando a política de uso de tiles.
