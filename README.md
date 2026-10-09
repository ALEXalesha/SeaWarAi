<div align="center">

# Sea Battle vs AI

**Classic Russian sea battle (Battleship) against an AI that computes where your ships are most likely to be. The AI never sees your board: it only gets the results of its own shots, and a law test checks it.**

[Русская версия](README.ru.md)

[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

</div>

Work in progress. See [CHANGELOG.md](CHANGELOG.md).

## Rules

- 10 × 10 board, columns A-J, rows 1-10.
- Russian fleet: one 4-deck ship, two 3-deck, three 2-deck, four 1-deck. Ships never touch, not even by corners (an option allows corner contact).
- A hit gives another shot. Cells around a sunk ship are marked automatically.
- Salvo option: as many shots per turn as you have ships afloat.

## License

MIT, see [LICENSE](LICENSE).
