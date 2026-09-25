"""Guards the metadata parsers against super-linear cost on untrusted content.

Asserts a ratio between adversarial and benign input of the same length, never a duration,
so a loaded machine cannot make it flake.
"""

import time

import pytest

from app import meta

# A linear pattern keeps the ratio stable as the input grows; a quadratic one blows it up.
# The margin is wide on purpose: it tells linear from quadratic, it does not measure
# performance, and it must not fail because the machine is busy.
MAX_RATIO = 8.0


def _time(fn, text: str) -> float:
    """Best of three: on a noisy machine the median misleads more than the minimum."""
    best = float("inf")
    for _ in range(3):
        t0 = time.perf_counter()
        fn(text)
        best = min(best, time.perf_counter() - t0)
    return best


def _adversarial(n: int) -> str:
    """Repeated `[[` and a tail that never closes, so every position starts a scan."""
    return "[[" * n + "a" * n


def _benign(n: int) -> str:
    """Same length, real wikilinks."""
    out = "[[destino]]" * (3 * n // 11)
    return out[: 3 * n]


@pytest.mark.parametrize("n", [2000, 4000])
def test_wikilinks_cost_no_more_on_adversarial_content(n):
    adv, benign = _adversarial(n), _benign(n)
    assert abs(len(adv) - len(benign)) <= 12, "las dos entradas deben medir lo mismo"

    t_adv = _time(meta.extract_links, adv)
    t_benign = _time(meta.extract_links, benign)

    ratio = t_adv / max(t_benign, 1e-6)
    assert ratio < MAX_RATIO, (
        f"extract_links cuesta {ratio:.0f}x más sobre contenido adverso de {len(adv)} bytes "
        f"({t_adv * 1000:.1f} ms frente a {t_benign * 1000:.1f} ms). "
        "Eso es retroceso super-lineal: cualquiera que pueda guardar una página puede "
        "quemar CPU del servidor."
    )


def test_cost_does_not_grow_with_size():
    """Doubling the input must double the cost, not quadruple it."""
    t1 = _time(meta.extract_links, _adversarial(2000))
    t2 = _time(meta.extract_links, _adversarial(4000))
    growth = t2 / max(t1, 1e-6)
    assert growth < 3.0, (
        f"doblar la entrada multiplicó el coste por {growth:.1f} (lineal ≈ 2, cuadrático ≈ 4)"
    )


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("[[destino]]", ["destino"]),
        ("[[destino|etiqueta]]", ["destino"]),
        ("[[con espacios]]", ["con espacios"]),
        ("texto [[a]] y [[b|c]] fin", ["a", "b"]),
        ("[[acentuación y ñ]]", ["acentuación y ñ"]),
    ],
)
def test_the_fix_did_not_change_what_a_wikilink_is(content, expected):
    """The fix is about cost, not meaning: what was recognised still is."""
    assert meta.extract_links(content) == expected


def test_a_target_longer_than_the_bound_is_not_a_target():
    """A wikilink target is a title, not a document."""
    assert meta.extract_links("[[" + "a" * 201 + "]]") == []
    assert meta.extract_links("[[" + "a" * 200 + "]]") == ["a" * 200]


def test_other_metadata_parsers_are_linear_too():
    """Tags and frontmatter run over the same untrusted content."""
    for fn in (meta.extract_tags, meta.strip_code):
        t1 = _time(fn, _adversarial(2000))
        t2 = _time(fn, _adversarial(4000))
        growth = t2 / max(t1, 1e-6)
        assert growth < 3.0, f"{fn.__name__} creció {growth:.1f}x al doblar la entrada"
