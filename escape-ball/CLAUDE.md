# Escape Ball: instruções para o Claude

- O código segue Clean Architecture + SOLID. Antes de commitar, abrir PR ou quando pedirem revisão, use a skill `revisao-clean-architecture` (`.claude/skills/revisao-clean-architecture/SKILL.md`).
- Checagens rápidas:
  - `flutter analyze && flutter test`
  - `cd functions && npm test`
- Os testes `test/architecture_test.dart` e `functions/test/architecture.test.ts` impõem a regra de dependências. Se falharem, conserte o código, não o teste.
- Mudou a física ou as constantes em `lib/domain/game/arena.dart`? Rode `dart run tool/gen_seeds.dart`.
