#!/usr/bin/env python3
"""Fix missing Portuguese accents in pt-BR text.

Can be used as:
1. Standalone script: fix accents in JSON/SQL files
2. Library: import apply_word_replacements, apply_phrase_replacements
"""
import json
import re
import sys
from pathlib import Path

# =============================================================================
# UNAMBIGUOUS word replacements (always need accent, no context needed)
# =============================================================================
WORD_MAP = {
    # -ão / -ões
    "Guardiao": "Guardião", "guardiao": "guardião",
    "Divisao": "Divisão", "divisao": "divisão",
    "Expansao": "Expansão", "expansao": "expansão",
    "comeco": "começo", "Comeco": "Começo",
    "comecar": "começar",
    "comecou": "começou",
    "comecaram": "começaram",
    "portao": "portão", "Portao": "Portão",
    "portoes": "portões",
    "inversao": "inversão",
    "direcao": "direção",
    "intencao": "intenção",
    "conclusao": "conclusão",
    "proporcao": "proporção",
    "compreensao": "compreensão",
    "questao": "questão",
    "visao": "visão",
    "Salao": "Salão", "salao": "salão",
    "missao": "missão",
    "traicao": "traição",
    "revelacao": "revelação",
    "proporcoes": "proporções", "Proporcoes": "Proporções",
    "versoes": "versões",
    "bilhoes": "bilhões",

    # -ção / -ções
    "operacao": "operação", "Operacao": "Operação",
    "falsificacao": "falsificação",
    "comunicacao": "comunicação",
    "organizacao": "organização",
    "classificacao": "classificação",
    "transmissao": "transmissão",
    "interceptacao": "interceptação",
    "decodificacao": "decodificação",
    "codificacao": "codificação",
    "substituicao": "substituição",

    # -ência / -ância / silêncio
    "silencio": "silêncio", "Silencio": "Silêncio",
    "Silicio": "Silício",

    # Proparoxítonas & esdrúxulas
    "mitica": "mítica",
    "milenios": "milênios",
    "subterraneo": "subterrâneo",
    "hieroglificos": "hieroglíficos",
    "hieroglificas": "hieroglíficas",
    "arquitetonico": "arquitetônico",
    "geotermica": "geotérmica",
    "logicos": "lógicos", "Logicas": "Lógicas", "logicas": "lógicas",
    "cosmico": "cósmico",
    "ordinario": "ordinário",
    "intermediario": "intermediário",
    "intermediaria": "intermediária",
    "penultimo": "penúltimo",
    "quantica": "quântica",
    "especificas": "específicas", "especifico": "específico",
    "binarias": "binárias", "binaria": "binária",
    "indivisiveis": "indivisíveis",
    "divisiveis": "divisíveis",
    "inabalavel": "inabalável",
    "inquebravel": "inquebrável",
    "maiusculas": "maiúsculas",

    # Nouns/adjectives
    "superficie": "superfície",
    "ruinas": "ruínas", "Ruinas": "Ruínas",
    "arvores": "árvores",
    "botanico": "botânico", "Botanico": "Botânico",
    "Botanica": "Botânica", "botanica": "botânica",
    "fisica": "física", "Fisica": "Física",
    "oleo": "óleo",
    "lagrimas": "lágrimas",
    "maos": "mãos",
    "manha": "manhã",
    "ceu": "céu", "ceus": "céus",
    "solida": "sólida",
    "tracos": "traços",
    "camaras": "câmaras",
    "tabuas": "tábuas",
    "espacamento": "espaçamento",
    "orcamento": "orçamento",
    "gramatica": "gramática",
    "digitos": "dígitos",
    "espacos": "espaços",
    "raciocinio": "raciocínio",
    "ingles": "inglês",
    "portugues": "português",
    "Bussola": "Bússola", "bussola": "bússola",
    "diaria": "diária",
    "joia": "jóia",
    "critico": "crítico", "critica": "crítica",
    "comite": "comitê",
    "maquina": "máquina",
    "insignia": "insígnia",
    "contrario": "contrário",
    "secundario": "secundário",
    "acessivel": "acessível",
    "senior": "sênior",
    "estagio": "estágio", "estagios": "estágios",
    "mantem": "mantém",
    "obtem": "obtém",
    "revelara": "revelará",
    "construida": "construída",
    "reconstruidas": "reconstruídas",
    "alcancar": "alcançar",
    "substituida": "substituída",
    "atraves": "através",
    "suico": "suíço", "suica": "suíça",
    "Suico": "Suíço", "Suica": "Suíça",

    # Verbs (unambiguous)
    "sera": "será",
    "serao": "serão",

    # Department names
    "Arqueologica": "Arqueológica",
    "Teorica": "Teórica",
    "Filosofica": "Filosófica",
    "Metaforas": "Metáforas",
    "Poeticos": "Poéticos",
    "Nostalgica": "Nostálgica",
    "Epicas": "Épicas",
    "Comecos": "Começos",
    "Criptograficas": "Criptográficas",
    "Criptograficos": "Criptográficos",
    "Numerica": "Numérica",
    "Matematica": "Matemática",
    "Cococentrica": "Cococêntrica",

    # Misc
    "tao ": "tão ",
    "explica-la": "explicá-la",
    "parametro": "parâmetro", "parametros": "parâmetros",
    "cirilico": "cirílico",
    "pedacos": "pedaços",
    "executavel": "executável",
    "clausula": "cláusula",
    "obvia": "óbvia",
    "identicos": "idênticos",
    "identicas": "idênticas",
    "leiloes": "leilões",
    "matematicos": "matemáticos",
    "caracteristicos": "característicos",
    "ciberseguranca": "cibersegurança",
    "lideranca": "liderança",
    "seguranca": "segurança",
    "confianca": "confiança",
    "alianca": "aliança",
    "vizinhanca": "vizinhança",
    "Cerimonia": "Cerimônia", "cerimonia": "cerimônia",
    "atomico": "atômico",
    "espaco": "espaço",
    "imperio": "império", "Imperio": "Império",
    "frances": "francês",
    "uniao": "união", "Uniao": "União",
    "limao": "limão",
    "nucleo": "núcleo",

    # ==========================================================================
    # MEDICAL / Dr. Cocada M.D. terms
    # ==========================================================================

    # -tico/-tica (proparoxítonas médicas)
    "diagnostico": "diagnóstico", "Diagnostico": "Diagnóstico",
    "diagnosticos": "diagnósticos",
    "prognostico": "prognóstico", "Prognostico": "Prognóstico",
    "sintomatico": "sintomático",
    "assintomatico": "assintomático",
    "patologico": "patológico", "patologica": "patológica",
    "epidemiologico": "epidemiológico", "epidemiologica": "epidemiológica",
    "clinico": "clínico", "clinica": "clínica",
    "cronico": "crônico", "cronica": "crônica",
    "toxico": "tóxico", "toxica": "tóxica",
    "genetico": "genético", "genetica": "genética",
    "terapeutico": "terapêutico", "terapeutica": "terapêutica",
    "farmaceutico": "farmacêutico", "farmaceutica": "farmacêutica",
    "antibiotico": "antibiótico", "antibioticos": "antibióticos",
    "anestesico": "anestésico",
    "analgesico": "analgésico",
    "metabolico": "metabólico", "metabolica": "metabólica",
    "neurologico": "neurológico", "neurologica": "neurológica",
    "cardiologico": "cardiológico",
    "oncologico": "oncológico",
    "ortopedico": "ortopédico",
    "oftalmologico": "oftalmológico",
    "psiquiatrico": "psiquiátrico",
    "pediatrico": "pediátrico",
    "cirurgico": "cirúrgico", "cirurgica": "cirúrgica",
    "sistolico": "sistólico",
    "diastolico": "diastólico",

    # -ção/-ções (termos médicos)
    "prescricao": "prescrição", "Prescricao": "Prescrição",
    "infeccao": "infecção", "infeccoes": "infecções",
    "medicacao": "medicação",
    "dosificacao": "dosificação",
    "administracao": "administração",
    "reabilitacao": "reabilitação",
    "hospitalizacao": "hospitalização",
    "transfusao": "transfusão",
    "incubacao": "incubação",
    "vacinacao": "vacinação",
    "desidratacao": "desidratação",
    "intoxicacao": "intoxicação",
    "contaminacao": "contaminação",
    "esterilizacao": "esterilização",

    # -ência/-ância (termos médicos)
    "emergencia": "emergência", "Emergencia": "Emergência",
    "frequencia": "frequência",
    "resistencia": "resistência",
    "incidencia": "incidência",
    "prevalencia": "prevalência",
    "convalescencia": "convalescência",
    "deficiencia": "deficiência",
    "insuficiencia": "insuficiência",
    "vigilancia": "vigilância",
    "tolerancia": "tolerância",
    "substancia": "substância",

    # Substantivos/adjetivos médicos
    "medico": "médico", "Medico": "Médico",
    "medica": "médica", "Medica": "Médica",
    "medicos": "médicos",
    "farmacia": "farmácia", "Farmacia": "Farmácia",
    "ciencia": "ciência",
    "virus": "vírus", "Virus": "Vírus",
    "analise": "análise", "Analise": "Análise",
    "analises": "análises",
    "orgao": "órgão", "orgaos": "órgãos",
    "prontuario": "prontuário", "Prontuario": "Prontuário",
    "laboratorio": "laboratório", "Laboratorio": "Laboratório",
    "ambulatorio": "ambulatório",
    "consultorio": "consultório",
    "obito": "óbito",
    "oxigenio": "oxigênio",
    "calcio": "cálcio",
    "potassio": "potássio",
    "sodio": "sódio",
    "magnesio": "magnésio",
    "leucocitos": "leucócitos",
    "eritrocitos": "eritrócitos",
    "celula": "célula", "celulas": "células",
    "bacterias": "bactérias", "bacteria": "bactéria",
    "sindrome": "síndrome", "Sindrome": "Síndrome",
    "ulcera": "úlcera",
    "valvula": "válvula",
    "capsulas": "cápsulas", "capsula": "cápsula",
    "protese": "prótese",
    "estetoscopio": "estetoscópio",
    "termometro": "termômetro",
    "oximetro": "oxímetro",
}

# =============================================================================
# CONTEXTUAL phrase replacements (ambiguous words need surrounding context)
# =============================================================================

# "e" → "é" (verb ser/estar) — only in safe contexts
E_VERB_PHRASES = [
    (r'\bnão e\b', 'não é'),
    (r'\bque e\b', 'que é'),
    (r'\bEste e\b', 'Este é'),
    (r'\beste e\b', 'este é'),
    (r'\bEsta e\b', 'Esta é'),
    (r'\bEsse e\b', 'Esse é'),
    (r'\bIsto e\b', 'Isto é'),
    (r'\bIsso e\b', 'Isso é'),
    (r'\bTudo e\b', 'Tudo é'),
    (r'\btudo e\b', 'tudo é'),
    (r'\bE perfeito\b', 'É perfeito'),
    (r'\bE ancestral\b', 'É ancestral'),
    (r'\bE o comeco\b', 'É o começo'),
    (r'\bE o fim\b', 'É o fim'),
    (r' e eterno\b', ' é eterno'),
    (r' e lenda\b', ' é lenda'),
    (r' e genuinamente\b', ' é genuinamente'),
    (r' e factualmente\b', ' é factualmente'),
    (r' e sempre\b', ' é sempre'),
    (r' e perfeita\b', ' é perfeita'),
    (r' e circular\b', ' é circular'),
    (r' e auto-inverso\b', ' é auto-inverso'),
    (r' e base 2\b', ' é base 2'),
    (r"final e preenchimento\b", "final é preenchimento"),
    (r' e protegida\b', ' é protegida'),
    (r' e invertida\b', ' é invertida'),
    (r' e marcado\b', ' é marcado'),
    (r' e guardada\b', ' é guardada'),
    (r' e digno\b', ' é digno'),
    (r' e ladeado\b', ' é ladeado'),
    (r' e mapeada\b', ' é mapeada'),
    (r' e substituída\b', ' é substituída'),
    (r' e sagrado\b', ' é sagrado'),
    (r' e visível\b', ' é visível'),
    (r' e considerada\b', ' é considerada'),
    (r' e seu\b', ' é seu'),
    (r' e sua\b', ' é sua'),
    (r'\btambém e\b', 'também é'),
    (r"A resposta e '", "A resposta é '"),
    (r"A chave e '", "A chave é '"),
    (r"O texto decodificado e '", "O texto decodificado é '"),
    (r"A decodificação completa e '", "A decodificação completa é '"),
    (r"insiste que e '", "insiste que é '"),
    (r"ao contrário e '", "ao contrário é '"),
    (r"contrário e '", "contrário é '"),
    (r"no final e uma dica\b", "no final é uma dica"),
    (r' e um termo\b', ' é um termo'),
    (r' e um caso\b', ' é um caso'),
    (r' e um cifrado\b', ' é um cifrado'),
    (r' e um número\b', ' é um número'),
    (r' e uma operação\b', ' é uma operação'),
    (r' e uma palavra\b', ' é uma palavra'),
    (r' e uma cifra\b', ' é uma cifra'),
    (r'XOR e uma operação', 'XOR é uma operação'),
    (r'XOR e seu próprio', 'XOR é seu próprio'),
    (r'XOR e 0x07', 'XOR é 0x07'),
    (r'A chave XOR e ', 'A chave XOR é '),
    (r'A camada externa e uma', 'A camada externa é uma'),
    (r'A camada externa e codificação', 'A camada externa é codificação'),
    (r'A camada interna e mais', 'A camada interna é mais'),
    (r'A camada interna e hex', 'A camada interna é hex'),
    (r'"E isso\.', '"É isso.'),
    (r'\bNem tudo e\b', 'Nem tudo é'),
    (r'\bporque e\b', 'porque é'),
    (r'charset e A', 'charset é A'),
    (r'diz que e ', 'diz que é '),
    (r'ROT13 e uma\b', 'ROT13 é uma'),
    (r'ROT13 e seu\b', 'ROT13 é seu'),
    (r'A1Z26 e uma\b', 'A1Z26 é uma'),
    (r'Atbash e uma\b', 'Atbash é uma'),
    (r'Base64 e uma\b', 'Base64 é uma'),
    (r'\bvitória e sua\b', 'vitória é sua'),
    (r'\bCada letra e\b', 'Cada letra é'),
    (r'A grade e numerada\b', 'A grade é numerada'),
    (r'alfabeto e invertido\b', 'alfabeto é invertido'),
    (r'na verdade e um\b', 'na verdade é um'),
    (r'\bFaca XOR\b', 'Faça XOR'),
    (r'\bfaca XOR\b', 'faça XOR'),
    (r'\bFaca uma\b', 'Faça uma'),
    (r'\bfaca uma\b', 'faça uma'),
    (r'\bVocê ve\b', 'Você vê'),
    (r'\bvocê ve\b', 'você vê'),
    (r'\bque você ve\b', 'que você vê'),
]

# "esta" → "está" (verb estar) — only in safe contexts
ESTA_VERB_PHRASES = [
    (r'\besta sendo\b', 'está sendo'),
    (r'\besta lendo\b', 'está lendo'),
    (r'\besta prestes\b', 'está prestes'),
    (r'\besta diante\b', 'está diante'),
    (r'\besta codificada\b', 'está codificada'),
    (r'\besta codificado\b', 'está codificado'),
    (r'\besta inscrita\b', 'está inscrita'),
    (r'\besta inscrito\b', 'está inscrito'),
    (r'\besta enterrada\b', 'está enterrada'),
    (r'\besta emoldurada\b', 'está emoldurada'),
    (r'\besta escondida\b', 'está escondida'),
    (r'\besta escondido\b', 'está escondido'),
    (r'\besta escrita\b', 'está escrita'),
    (r'\besta selado\b', 'está selado'),
    (r'\besta relacionada\b', 'está relacionada'),
    (r'\besta quase\b', 'está quase'),
    (r'\besta completa\b', 'está completa'),
    (r'\besta pensando\b', 'está pensando'),
    (r'\besta ao\b', 'está ao'),
    (r'\bVocê esta\b', 'Você está'),
    (r'\bvocê esta\b', 'você está'),
    (r'\bjá esta\b', 'já está'),
    (r'\bnão esta\b', 'não está'),
    (r'\bcoco esta\b', 'coco está'),
    (r'\besta nos dados\b', 'está nos dados'),
    (r'labirinto esta a\b', 'labirinto está a'),
    (r'domínio esta codificado\b', 'domínio está codificado'),
    (r'mensagem esta codificada\b', 'mensagem está codificada'),
    (r'A mensagem esta codificada\b', 'A mensagem está codificada'),
    (r'resultado intermediário esta codificado\b', 'resultado intermediário está codificado'),
    (r'portão esta o\b', 'portão está o'),
    (r'espiral esta o\b', 'espiral está o'),
    (r'que esta a mesma\b', 'que está a mesma'),
]

# "la" → "lá" (adverb) — only in safe contexts
LA_PHRASES = [
    (r'\bla na\b', 'lá na'),
    (r'\bla no\b', 'lá no'),
    (r'\bla dentro\b', 'lá dentro'),
    (r'\bLa dentro\b', 'Lá dentro'),
    (r'\bestamos la\b', 'estamos lá'),
    (r'\bestaremos la\b', 'estaremos lá'),
    (r'\bcolocado la\b', 'colocado lá'),
    (r'\bcolocados la\b', 'colocados lá'),
    (r'\bquase la\b', 'quase lá'),
]

# "nos" → "nós" (pronoun) — only in safe contexts
NOS_PHRASES = [
    (r'\bnos fizemos\b', 'nós fizemos'),
    (r'\bnos estaremos\b', 'nós estaremos'),
    (r'\bantes de nos\b', 'antes de nós'),
]

# "contem" → "contém" — safe context (verb "conter")
CONTEM_PHRASES = [
    (r'\bcontem um\b', 'contém um'),
    (r'\bcontem uma\b', 'contém uma'),
    (r'\bcontem dados\b', 'contém dados'),
    (r'\bcontem fragmentos\b', 'contém fragmentos'),
    (r'\bcontem as\b', 'contém as'),
    (r'\bcontem os\b', 'contém os'),
    (r'\bcontem tabuas\b', 'contém tábuas'),
    (r'\bcontem registros\b', 'contém registros'),
    (r'\bcontem informações\b', 'contém informações'),
]


def apply_word_replacements(text: str) -> str:
    """Apply unambiguous word-level replacements."""
    for old, new in WORD_MAP.items():
        if old.endswith(' '):
            text = text.replace(old, new)
        else:
            pattern = r'\b' + re.escape(old) + r'\b'
            text = re.sub(pattern, new, text)
    return text


def apply_phrase_replacements(text: str) -> str:
    """Apply contextual phrase replacements for ambiguous words."""
    all_phrases = (
        E_VERB_PHRASES +
        ESTA_VERB_PHRASES +
        LA_PHRASES +
        NOS_PHRASES +
        CONTEM_PHRASES
    )
    for pattern, replacement in all_phrases:
        text = re.sub(pattern, replacement, text)
    return text


# =============================================================================
# Standalone file-fixing utilities
# =============================================================================

def fix_file(filepath: Path, dry_run: bool = False) -> int:
    """Fix accents in a single JSON file. Returns count of changes."""
    with open(filepath, 'r', encoding='utf-8') as f:
        original = f.read()

    fixed = apply_word_replacements(original)
    fixed = apply_phrase_replacements(fixed)

    if original == fixed:
        print(f"  {filepath.name}: no changes needed")
        return 0

    changes = 0
    orig_lines = original.split('\n')
    fixed_lines = fixed.split('\n')
    for i, (o, n) in enumerate(zip(orig_lines, fixed_lines)):
        if o != n:
            changes += 1
            if dry_run:
                print(f"  L{i+1}:")
                print(f"    - {o.strip()[:140]}")
                print(f"    + {n.strip()[:140]}")

    if not dry_run:
        try:
            json.loads(fixed)
        except json.JSONDecodeError as e:
            print(f"  ERROR: Invalid JSON after fixes in {filepath.name}: {e}")
            return 0
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(fixed)
        print(f"  {filepath.name}: {changes} lines changed")
    else:
        print(f"  {filepath.name}: {changes} lines would change")

    return changes


def _extract_pt_br_segments(text: str) -> list[tuple[int, int]]:
    """Find start/end positions of pt_BR content within JSONB SQL strings."""
    segments = []
    for m in re.finditer(r'"pt_BR"\s*:\s*\{', text):
        start = m.start()
        depth = 0
        pos = m.end() - 1
        for i in range(pos, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    segments.append((start, i + 1))
                    break
    for m in re.finditer(r'"pt_BR"\s*:\s*"', text):
        start = m.start()
        pos = m.end()
        while pos < len(text):
            if text[pos] == '"' and text[pos - 1] != '\\':
                segments.append((start, pos + 1))
                break
            pos += 1
    return segments


def fix_sql_file(filepath: Path, dry_run: bool = False) -> int:
    """Fix accents in a SQL seed file (only pt_BR JSONB text). Returns count of changes."""
    with open(filepath, 'r', encoding='utf-8') as f:
        original = f.read()

    segments = _extract_pt_br_segments(original)
    if not segments:
        print(f"  {filepath.name}: no pt_BR segments found")
        return 0

    result_parts = []
    last_end = 0
    total_changes = 0

    for seg_start, seg_end in sorted(segments):
        result_parts.append(original[last_end:seg_start])
        segment = original[seg_start:seg_end]
        fixed_segment = apply_word_replacements(segment)
        fixed_segment = apply_phrase_replacements(fixed_segment)
        if fixed_segment != segment:
            total_changes += 1
            if dry_run:
                for old_line, new_line in zip(segment.split('\n'), fixed_segment.split('\n')):
                    if old_line != new_line:
                        print(f"    - {old_line.strip()[:120]}")
                        print(f"    + {new_line.strip()[:120]}")
        result_parts.append(fixed_segment)
        last_end = seg_end

    result_parts.append(original[last_end:])
    fixed_text = ''.join(result_parts)

    if fixed_text == original:
        print(f"  {filepath.name}: no changes needed")
        return 0

    if not dry_run:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(fixed_text)
        print(f"  {filepath.name}: {total_changes} pt_BR segments changed")
    else:
        print(f"  {filepath.name}: {total_changes} pt_BR segments would change")

    return total_changes


def main():
    """Standalone CLI: fix accents in JSON/SQL files."""
    dry_run = '--dry-run' in sys.argv

    if dry_run:
        print("=== DRY RUN MODE ===\n")
    else:
        print("=== APPLYING ACCENT FIXES ===\n")

    # Accept file paths as positional args
    files = [Path(a) for a in sys.argv[1:] if not a.startswith('--')]
    if not files:
        print("Usage: fix_accents.py [--dry-run] <file1.json> [file2.sql] ...")
        print("  Fixes missing pt-BR accents in JSON or SQL files.")
        sys.exit(1)

    total = 0
    for f in files:
        if not f.exists():
            print(f"  {f}: not found, skipping")
            continue
        if f.suffix == '.sql':
            total += fix_sql_file(f, dry_run)
        else:
            total += fix_file(f, dry_run)

    print(f"\nTotal: {total} {'would change' if dry_run else 'changed'}")


if __name__ == '__main__':
    main()
