from app.language import is_english
from app.summarizer import count_words, trim_to_word_limit, validate_extractive

SOURCE = (
    "The company opened three new offices in 2025. Revenue rose by 12 percent.\n"
    "Employee satisfaction stayed   flat. The board approved a new strategy."
)


def test_verbatim_sentences_are_kept_and_paraphrases_rejected():
    kept, rejected = validate_extractive(
        ["The company opened three new offices in 2025.", "Revenue went up 12%.", "Employee satisfaction stayed flat."],
        SOURCE,
    )
    assert kept == ["The company opened three new offices in 2025.", "Employee satisfaction stayed flat."]
    assert rejected == 1


def test_extractive_respects_word_limit():
    kept, _ = validate_extractive(
        ["The company opened three new offices in 2025.", "Revenue rose by 12 percent."], SOURCE, limit=9
    )
    assert kept == ["The company opened three new offices in 2025."]


def test_duplicate_sentences_are_dropped():
    kept, _ = validate_extractive(["Revenue rose by 12 percent.", "Revenue rose by 12 percent."], SOURCE)
    assert kept == ["Revenue rose by 12 percent."]


def test_trim_ends_on_sentence_boundary():
    text = "One two three. Four five six. Seven eight nine."
    assert trim_to_word_limit(text, limit=7) == "One two three. Four five six."


def test_trim_leaves_short_text_alone():
    assert trim_to_word_limit("Short text.", limit=350) == "Short text."


def test_trim_never_exceeds_350_words():
    long_text = " ".join(f"Sentence number {i} is here." for i in range(200))
    assert count_words(trim_to_word_limit(long_text)) <= 350


def test_language_detection():
    english = "The committee reviewed the annual budget and agreed to increase funding for public schools next year."
    french = "Le comité a examiné le budget annuel et a accepté d'augmenter le financement des écoles publiques."
    assert is_english(english)
    assert not is_english(french)
