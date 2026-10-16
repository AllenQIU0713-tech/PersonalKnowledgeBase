"""Fail-closed orchestration for question-specific evidence review."""
from dataclasses import dataclass
import hashlib
import json

from .evidence_review import ReviewError, ReviewInput, business_identifier_gate


PIPELINE_VERSION = 's2r3-evidence-gate-v1'
MAX_REVIEWED_SOURCES = 6
MAX_PER_DOCUMENT = 2
MAX_CONTEXT_CHARS = 6000
MAX_SOURCE_CHARS = 1200


class EvidenceUnavailable(ValueError):
    """The evidence gate cannot safely produce a question context."""


def _digest(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(',', ':')).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ReviewedSnapshot:
    question_sha256: str
    index_signature: str
    index_generation: int
    index_revision: int
    pipeline_version: str
    reviewer_signature: str
    sources: tuple
    related_sources: tuple
    snapshot_sha256: str


class EvidencePipeline:
    """Review retrieved passages through an explicitly injected local reviewer.

    The reviewer is deliberately not constructed here. Production remains
    unavailable until a separately qualified reviewer is explicitly wired.
    Test tasks may inject their own deterministic double in an isolated fixture.
    """

    def __init__(self, reviewer, reviewer_signature, pipeline_version=PIPELINE_VERSION):
        if reviewer is None:
            raise EvidenceUnavailable('evidence_reviewer_unavailable')
        if not isinstance(reviewer_signature, str) or not reviewer_signature.strip():
            raise EvidenceUnavailable('evidence_reviewer_signature_missing')
        if pipeline_version != PIPELINE_VERSION:
            raise EvidenceUnavailable('evidence_pipeline_version_mismatch')
        self.reviewer = reviewer
        self.reviewer_signature = reviewer_signature
        self.pipeline_version = pipeline_version

    def review(self, question, candidates, index):
        if not isinstance(question, str) or not question.strip():
            raise EvidenceUnavailable('invalid_question')
        if not isinstance(candidates, (list, tuple)) or len(candidates) > 40:
            raise EvidenceUnavailable('invalid_candidate_snapshot')
        required_index = ('signature', 'generation', 'revision')
        if not isinstance(index, dict) or any(key not in index for key in required_index):
            raise EvidenceUnavailable('invalid_index_snapshot')

        accepted, related = [], []
        question = question.strip()
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise EvidenceUnavailable('invalid_candidate')
            passage_id = candidate.get('chunk_id')
            document_id = candidate.get('id')
            body = candidate.get('text')
            title = candidate.get('title')
            if (not isinstance(passage_id, str) or not passage_id or
                    not isinstance(document_id, str) or not document_id or
                    not isinstance(body, str) or not body or
                    not isinstance(title, str)):
                raise EvidenceUnavailable('invalid_candidate_fields')
            local = {
                'document_id': document_id, 'chunk_id': passage_id,
                'title': title, 'page': candidate.get('page'),
                'text': body[:MAX_SOURCE_CHARS],
                'source_type': candidate.get('source_type'),
                'source_label': candidate.get('source_label'),
                'content_version': candidate.get('content_version'),
                'qualification_version': candidate.get('qualification_version'),
                'source_hash': candidate.get('source_hash'),
                'semantic_similarity': candidate.get('semantic_similarity'),
                'fused_score': candidate.get('fused_score'),
            }
            if candidate.get('privacy') != 'allowed':
                # Never echo restricted content through the QA preview response.
                continue
            if candidate.get('question_state') not in (None, 'ready'):
                related.append(dict(local, review_state='ineligible'))
                continue
            if candidate.get('source_type') not in ('collected', 'legacy_memory'):
                related.append(dict(local, review_state='invalid_source_type'))
                continue
            identifier_match, missing_ids = business_identifier_gate(question, title, body)
            if not identifier_match:
                related.append(dict(local, review_state='business_identifier_mismatch',
                                    missing_business_ids=missing_ids))
                continue
            if len(body) > MAX_SOURCE_CHARS:
                related.append(dict(local, review_state='passage_exceeds_review_limit'))
                continue

            item = ReviewInput(
                query_id=hashlib.sha256(question.encode()).hexdigest(),
                passage_id=passage_id, question=question, title=title, body=body,
                content_version=candidate.get('content_version'),
                qualification_version=candidate.get('qualification_version'))
            try:
                item.validate()
            except ReviewError:
                related.append(dict(local, review_state='invalid_review_input'))
                continue
            try:
                result = self.reviewer.review(item)
                if not isinstance(result, dict):
                    raise ReviewError('invalid_reviewer_result')
                if (result.get('question_sha256') != item.question_hash or
                        result.get('evidence_sha256') != item.evidence_hash or
                        result.get('passage_id') != passage_id or
                        result.get('content_version') != item.content_version or
                        result.get('qualification_version') != item.qualification_version or
                        result.get('config_signature') != self.reviewer_signature):
                    raise EvidenceUnavailable('reviewer_snapshot_mismatch')
                if result.get('gate') == 'reviewer_failure':
                    raise EvidenceUnavailable('evidence_reviewer_runtime_unavailable')
                output = result.get('reviewer_output')
                quotes = output.get('evidence_quotes') if isinstance(output, dict) else None
                accepted_result = (
                    result.get('accepted') is True and
                    output.get('verdict') == 'supported' and
                    isinstance(quotes, list) and bool(quotes) and
                    all(isinstance(quote, str) and quote and quote in body for quote in quotes))
                if not accepted_result:
                    reason = ('invalid_verbatim_quote'
                              if result.get('accepted') is True else
                              result.get('gate', 'rejected'))
                    related.append(dict(local, review_state=reason))
                    continue
                if (sum(len(quote) for quote in quotes) > MAX_SOURCE_CHARS or
                        any(quote not in local['text'] for quote in quotes)):
                    related.append(dict(local, review_state='quote_not_preserved'))
                    continue
                accepted.append(dict(local, text=local['text'], evidence_quote=quotes[0],
                                     evidence_quotes=list(quotes),
                                     review_state='supported',
                                     reviewer_signature=self.reviewer_signature,
                                     review_pipeline_version=self.pipeline_version))
            except EvidenceUnavailable:
                raise
            except Exception:
                # Do not expose reviewer diagnostics or passage content in the UI.
                raise EvidenceUnavailable('evidence_reviewer_runtime_unavailable') from None

        selected, document_counts, budget = [], {}, MAX_CONTEXT_CHARS
        for source in accepted:
            if len(selected) >= MAX_REVIEWED_SOURCES or budget <= 0:
                break
            count = document_counts.get(source['document_id'], 0)
            if count >= MAX_PER_DOCUMENT:
                continue
            text = source['text'][:min(MAX_SOURCE_CHARS, budget)]
            if any(quote not in text for quote in source['evidence_quotes']):
                continue
            selected.append(dict(source, text=text))
            document_counts[source['document_id']] = count + 1
            budget -= len(text)

        serializable = {
            'question_sha256': hashlib.sha256(question.encode()).hexdigest(),
            'index_signature': index['signature'],
            'index_generation': index['generation'],
            'index_revision': index['revision'],
            'pipeline_version': self.pipeline_version,
            'reviewer_signature': self.reviewer_signature,
            'sources': selected,
        }
        return ReviewedSnapshot(
            question_sha256=serializable['question_sha256'],
            index_signature=index['signature'],
            index_generation=index['generation'], index_revision=index['revision'],
            pipeline_version=self.pipeline_version,
            reviewer_signature=self.reviewer_signature,
            sources=tuple(selected), related_sources=tuple(related),
            snapshot_sha256=_digest(serializable))
