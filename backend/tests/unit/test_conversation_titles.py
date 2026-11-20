from askboard.services.conversations import TITLE_MAX, title_from_question


def test_short_question_is_kept():
    assert title_from_question("  Quanto cada\n cliente gastou? ") == "Quanto cada cliente gastou?"


def test_long_question_is_cut_at_a_word():
    title = title_from_question("Qual foi a receita total por categoria de produto em cada estado no último trimestre?")

    assert len(title) <= TITLE_MAX + 1
    assert title.endswith("…") and not title.endswith(" …")
    assert title.startswith("Qual foi a receita total por categoria")


def test_blank_question_gets_a_default():
    assert title_from_question("   ") == "New chat"
