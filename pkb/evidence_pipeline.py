"""Fail-closed orchestration for question-specific evidence review."""
from dataclasses import dataclass
import hashlib
import json
import time

from .evidence_review import ReviewError, ReviewInput, business_identifier_gate, configuration_signature


PIPELINE_VERSION = 's2r3-evidence-gate-v1'
RESULT_PROTOCOL_VERSION = 's2r3-evidence-set-review-v1'
MAX_REVIEWED_SOURCES = 6
MAX_PER_DOCUMENT = 2
MAX_CONTEXT_CHARS = 6000
MAX_SOURCE_CHARS = 1200
MAX_SET_BATCH_EXTRAS = 2
MAX_SET_REVIEW_BATCHES = 20
MAX_SET_BATCH_CHARS = 16000
MAX_SET_TOTAL_CHARS = 300000
MAX_SET_REVIEW_SECONDS = 120.0


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
    conflicts: tuple
    rejection_counts: dict
    set_review_batches: tuple
    conflict_state: str
    snapshot_sha256: str


class EvidencePipeline:
    """Review passages and their evidence set using one injected local reviewer.

    No reviewer factory is provided. Production stays unavailable until an
    independently qualified adapter is explicitly wired. Synthetic doubles
    belong to the isolated test task and are not model-quality evidence.
    """

    formally_qualified = False
    conflict_detection_state = 'candidate_only'

    def __init__(self, reviewer, pipeline_version=PIPELINE_VERSION):
        if reviewer is None:
            raise EvidenceUnavailable('evidence_reviewer_unavailable')
        if pipeline_version != PIPELINE_VERSION:
            raise EvidenceUnavailable('evidence_pipeline_version_mismatch')
        self.reviewer = reviewer
        self.pipeline_version = pipeline_version
        self.reviewer_manifest, self.reviewer_signature = self._read_reviewer_config()

    def _read_reviewer_config(self):
        manifest = getattr(self.reviewer, 'configuration', None)
        required = ('candidate', 'model_sha256', 'quantization', 'template_version',
                    'settings', 'pipeline_version', 'runtime_version',
                    'result_protocol_version')
        if (not isinstance(manifest, dict) or
                any(key not in manifest for key in required) or
                any(not isinstance(manifest[key], str) or not manifest[key].strip()
                    for key in required if key != 'settings') or
                not isinstance(manifest.get('settings'), dict)):
            raise EvidenceUnavailable('evidence_reviewer_manifest_invalid')
        model_sha256 = manifest['model_sha256']
        if (len(model_sha256) != 64 or
                any(char not in '0123456789abcdef' for char in model_sha256) or
                manifest['result_protocol_version'] != RESULT_PROTOCOL_VERSION):
            raise EvidenceUnavailable('evidence_reviewer_manifest_invalid')
        try:
            signature = configuration_signature(
                manifest['candidate'], model_sha256, manifest['quantization'],
                manifest['template_version'], manifest['settings'],
                manifest['pipeline_version'], manifest['runtime_version'],
                manifest['result_protocol_version'])
            frozen_manifest = json.loads(json.dumps(
                manifest, ensure_ascii=False, sort_keys=True))
        except (TypeError, ValueError):
            raise EvidenceUnavailable('evidence_reviewer_manifest_invalid') from None
        if getattr(self.reviewer, 'config_signature', None) != signature:
            raise EvidenceUnavailable('evidence_reviewer_signature_mismatch')
        return frozen_manifest, signature

    def _check_reviewer_config(self):
        manifest, signature = self._read_reviewer_config()
        if manifest != self.reviewer_manifest or signature != self.reviewer_signature:
            raise EvidenceUnavailable('evidence_reviewer_signature_mismatch')

    def assert_current(self):
        self._check_reviewer_config()

    @staticmethod
    def _count_rejection(counts, reason):
        safe_reason = reason if isinstance(reason, str) and reason.replace('_', '').isalnum() else 'rejected'
        counts[safe_reason] = counts.get(safe_reason, 0) + 1

    def _review_result(self, result, item):
        if not isinstance(result, dict):
            raise EvidenceUnavailable('invalid_reviewer_result')
        if (result.get('question_sha256') != item.question_hash or
                result.get('evidence_sha256') != item.evidence_hash or
                result.get('passage_id') != item.passage_id or
                result.get('content_version') != item.content_version or
                result.get('qualification_version') != item.qualification_version or
                result.get('config_signature') != self.reviewer_signature or
                result.get('pipeline_version') != self.reviewer_manifest['pipeline_version'] or
                result.get('runtime_version') != self.reviewer_manifest['runtime_version'] or
                result.get('result_protocol_version') !=
                self.reviewer_manifest['result_protocol_version']):
            raise EvidenceUnavailable('reviewer_snapshot_mismatch')
        if result.get('gate') == 'reviewer_failure':
            raise EvidenceUnavailable('evidence_reviewer_runtime_unavailable')
        output = result.get('reviewer_output')
        if not isinstance(output, dict):
            return None, 'invalid_reviewer_output'
        quotes = output.get('evidence_quotes')
        if (result.get('accepted') is not True or output.get('verdict') != 'supported' or
                not isinstance(quotes, list) or not quotes or
                any(not isinstance(quote, str) or not quote.strip() or
                    not any(char.isalnum() for char in quote) or quote not in item.body
                    for quote in quotes)):
            return None, 'unsupported_or_invalid_quote'
        return list(quotes), None

    def _review_set(self, question, sources, proposed_source_ids, timeout_seconds):
        self._check_reviewer_config()
        selected_ids = set(proposed_source_ids)
        evidence = [{
            'source_id': source['chunk_id'],
            'document_id': source['document_id'],
            'title': source['title'],
            'source_type': source['source_type'],
            'source_label': source['source_label'],
            'evidence_quotes': list(source['evidence_quotes']),
            'role': 'proposed_answer_evidence'
            if source['chunk_id'] in selected_ids else 'remaining_supported_evidence',
        } for source in sources]
        proposed_ids = [source['chunk_id'] for source in sources
                        if source['chunk_id'] in selected_ids]
        remaining_ids = [source['chunk_id'] for source in sources
                         if source['chunk_id'] not in selected_ids]
        comparison_plan = {
            'within_proposed_pairs': [[proposed_ids[i], proposed_ids[j]]
                                      for i in range(len(proposed_ids))
                                      for j in range(i + 1, len(proposed_ids))],
            'proposed_vs_remaining_pairs': [[proposed, remaining]
                                            for proposed in proposed_ids
                                            for remaining in remaining_ids],
        }
        expected_pairs = (comparison_plan['within_proposed_pairs'] +
                          comparison_plan['proposed_vs_remaining_pairs'])
        question_hash = hashlib.sha256(question.encode()).hexdigest()
        plan_hash = _digest(comparison_plan)
        evidence_set_hash = _digest({'question_sha256': question_hash,
                                     'evidence': evidence,
                                     'comparison_plan': comparison_plan})
        batch_char_count = len(json.dumps({
            'question': question, 'evidence': evidence,
            'comparison_plan': comparison_plan,
        }, ensure_ascii=False, sort_keys=True, separators=(',', ':')))
        if batch_char_count > MAX_SET_BATCH_CHARS:
            return 'uncertain', []
        method = getattr(self.reviewer, 'review_set', None)
        if not callable(method):
            return 'unavailable', []
        try:
            result = method(question, evidence, comparison_plan,
                            timeout_seconds=timeout_seconds)
        except Exception:
            raise EvidenceUnavailable('evidence_set_reviewer_runtime_unavailable') from None
        self._check_reviewer_config()
        try:
            result_size = len(json.dumps(result, ensure_ascii=False,
                                         sort_keys=True, separators=(',', ':')))
        except (TypeError, ValueError):
            raise EvidenceUnavailable('invalid_evidence_set_review') from None
        if (result_size > MAX_SET_BATCH_CHARS or not isinstance(result, dict) or
                result.get('question_sha256') != question_hash or
                result.get('evidence_set_sha256') != evidence_set_hash or
                result.get('comparison_plan_sha256') != plan_hash or
                result.get('config_signature') != self.reviewer_signature or
                result.get('result_protocol_version') !=
                self.reviewer_manifest['result_protocol_version'] or
                result.get('source_ids') != [item['source_id'] for item in evidence]):
            raise EvidenceUnavailable('invalid_evidence_set_review')
        verdict, groups = result.get('verdict'), result.get('conflicts')
        if verdict not in ('consistent', 'conflict', 'uncertain') or not isinstance(groups, list):
            raise EvidenceUnavailable('invalid_evidence_set_review')
        checked_pairs = result.get('checked_pairs')
        if (not isinstance(checked_pairs, list) or
                any(pair not in expected_pairs for pair in checked_pairs) or
                (verdict == 'consistent' and checked_pairs != expected_pairs)):
            raise EvidenceUnavailable('invalid_evidence_set_coverage')
        source_map = {source['chunk_id']: source for source in sources}
        if verdict == 'consistent':
            if groups:
                raise EvidenceUnavailable('invalid_evidence_set_review')
            return verdict, []
        if verdict == 'uncertain':
            if groups:
                raise EvidenceUnavailable('invalid_evidence_set_review')
            return verdict, []
        if not groups:
            raise EvidenceUnavailable('invalid_evidence_set_review')

        normalized_groups = []
        for group in groups:
            if not isinstance(group, dict) or set(group) != {'evidence'}:
                raise EvidenceUnavailable('invalid_evidence_set_conflict')
            items = group['evidence']
            if not isinstance(items, list) or len(items) < 2:
                raise EvidenceUnavailable('invalid_evidence_set_conflict')
            normalized, seen = [], set()
            for item in items:
                if not isinstance(item, dict) or set(item) != {'source_id', 'quote'}:
                    raise EvidenceUnavailable('invalid_evidence_set_conflict')
                source_id, quote = item['source_id'], item['quote']
                source = source_map.get(source_id)
                if (source is None or source_id in seen or not isinstance(quote, str) or
                        not quote.strip() or not any(char.isalnum() for char in quote) or
                        quote not in source['evidence_quotes']):
                    raise EvidenceUnavailable('invalid_evidence_set_conflict')
                seen.add(source_id)
                normalized.append({
                    'document_id': source['document_id'], 'chunk_id': source_id,
                    'title': source['title'], 'source_type': source['source_type'],
                    'source_label': source['source_label'], 'page': source['page'],
                    'quote': quote,
                })
            if len(seen) < 2:
                raise EvidenceUnavailable('invalid_evidence_set_conflict')
            conflict_pairs = [[pair[0], pair[1]] for pair in expected_pairs
                              if pair[0] in seen and pair[1] in seen]
            if any(pair not in checked_pairs for pair in conflict_pairs):
                raise EvidenceUnavailable('invalid_evidence_set_conflict')
            normalized_groups.append({'evidence': normalized})
        return verdict, normalized_groups

    def review(self, question, candidates, index):
        if not isinstance(question, str) or not question.strip():
            raise EvidenceUnavailable('invalid_question')
        if not isinstance(candidates, (list, tuple)) or len(candidates) > 40:
            raise EvidenceUnavailable('invalid_candidate_snapshot')
        required_index = ('signature', 'generation', 'revision')
        if not isinstance(index, dict) or any(key not in index for key in required_index):
            raise EvidenceUnavailable('invalid_index_snapshot')
        self._check_reviewer_config()

        accepted, rejections = [], {}
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
            if candidate.get('privacy') != 'allowed':
                self._count_rejection(rejections, 'restricted_excluded')
                continue
            if candidate.get('question_state') not in (None, 'ready'):
                self._count_rejection(rejections, 'ineligible')
                continue
            if candidate.get('source_type') not in ('collected', 'legacy_memory'):
                self._count_rejection(rejections, 'invalid_source_type')
                continue
            identifier_match, _ = business_identifier_gate(question, title, body)
            if not identifier_match:
                self._count_rejection(rejections, 'business_identifier_mismatch')
                continue
            if len(body) > MAX_SOURCE_CHARS:
                self._count_rejection(rejections, 'passage_exceeds_review_limit')
                continue
            item = ReviewInput(
                query_id=hashlib.sha256(question.encode()).hexdigest(),
                passage_id=passage_id, question=question, title=title, body=body,
                content_version=candidate.get('content_version'),
                qualification_version=candidate.get('qualification_version'))
            try:
                item.validate()
            except ReviewError:
                self._count_rejection(rejections, 'invalid_review_input')
                continue
            self._check_reviewer_config()
            try:
                result = self.reviewer.review(item)
            except Exception:
                raise EvidenceUnavailable('evidence_reviewer_runtime_unavailable') from None
            self._check_reviewer_config()
            quotes, rejection = self._review_result(result, item)
            if rejection:
                self._count_rejection(rejections, rejection)
                continue
            accepted.append({
                'document_id': document_id, 'chunk_id': passage_id,
                'title': title, 'page': candidate.get('page'),
                'text': body, 'source_type': candidate['source_type'],
                'source_label': candidate.get('source_label'),
                'content_version': item.content_version,
                'qualification_version': item.qualification_version,
                'source_hash': candidate.get('source_hash'),
                'semantic_similarity': candidate.get('semantic_similarity'),
                'fused_score': candidate.get('fused_score'),
                'evidence_quotes': quotes,
                'review_state': 'supported',
                'reviewer_signature': self.reviewer_signature,
                'review_pipeline_version': self.pipeline_version,
            })

        selected, document_counts, budget = [], {}, MAX_CONTEXT_CHARS
        for source in accepted:
            if len(selected) >= MAX_REVIEWED_SOURCES or budget <= 0:
                self._count_rejection(rejections, 'context_budget_exceeded')
                continue
            count = document_counts.get(source['document_id'], 0)
            if count >= MAX_PER_DOCUMENT:
                self._count_rejection(rejections, 'document_source_limit')
                continue
            text = source['text'][:min(MAX_SOURCE_CHARS, budget)]
            if any(quote not in text for quote in source['evidence_quotes']):
                self._count_rejection(rejections, 'quote_not_preserved')
                continue
            selected.append(dict(source, text=text))
            document_counts[source['document_id']] = count + 1
            budget -= len(text)

        conflict_state, conflicts, set_review_batches = 'not_required', [], []
        answer_sources = selected
        if len(accepted) > 1 and not selected:
            conflict_state = 'uncertain'
            set_review_batches.append({
                'source_ids': [item['chunk_id'] for item in accepted],
                'evidence_set_sha256': None, 'input_char_count': 0,
                'verdict': 'uncertain', 'output': None,
                'reason_code': 'no_proposed_evidence_within_context_budget',
            })
        elif len(accepted) > 1 and selected:
            # Compare the proposed answer set internally, then in fixed batches
            # compare every remaining supported quote against that full set.
            selected_ids = {item['chunk_id'] for item in selected}
            remaining = [item for item in accepted if item['chunk_id'] not in selected_ids]
            batches = ([selected] if len(selected) > 1 else [])
            batches.extend(selected + remaining[start:start + MAX_SET_BATCH_EXTRAS]
                            for start in range(0, len(remaining), MAX_SET_BATCH_EXTRAS))
            total_chars, started = 0, time.monotonic()
            covered = set()
            conflict_state = 'consistent'
            if len(batches) > MAX_SET_REVIEW_BATCHES:
                conflict_state = 'uncertain'
                set_review_batches.append({
                    'source_ids': [item['chunk_id'] for item in accepted],
                    'evidence_set_sha256': None, 'input_char_count': 0,
                    'verdict': 'uncertain', 'output': None,
                    'reason_code': 'set_review_batch_count_exceeded',
                })
            else:
                for batch in batches:
                    batch_evidence = [{
                        'source_id': item['chunk_id'],
                        'document_id': item['document_id'],
                        'title': item['title'],
                        'source_type': item['source_type'],
                        'source_label': item['source_label'],
                        'evidence_quotes': item['evidence_quotes'],
                        'role': 'proposed_answer_evidence'
                        if item['chunk_id'] in selected_ids else 'remaining_supported_evidence',
                    } for item in batch]
                    proposed_ids = [item['chunk_id'] for item in batch
                                    if item['chunk_id'] in selected_ids]
                    remaining_ids = [item['chunk_id'] for item in batch
                                     if item['chunk_id'] not in selected_ids]
                    comparison_plan = {
                        'within_proposed_pairs': [[proposed_ids[i], proposed_ids[j]]
                                                  for i in range(len(proposed_ids))
                                                  for j in range(i + 1, len(proposed_ids))],
                        'proposed_vs_remaining_pairs': [[proposed, extra]
                                                        for proposed in proposed_ids
                                                        for extra in remaining_ids],
                    }
                    plan_hash = _digest(comparison_plan)
                    batch_hash = _digest({
                        'question_sha256': hashlib.sha256(question.encode()).hexdigest(),
                        'evidence': batch_evidence,
                        'comparison_plan': comparison_plan})
                    payload_size = len(json.dumps({
                        'question': question, 'evidence': batch_evidence,
                        'comparison_plan': comparison_plan}, ensure_ascii=False, sort_keys=True,
                        separators=(',', ':')))
                    total_chars += payload_size
                    batch_ids = [item['chunk_id'] for item in batch]
                    if payload_size > MAX_SET_BATCH_CHARS or total_chars > MAX_SET_TOTAL_CHARS:
                        conflict_state = 'uncertain'
                        set_review_batches.append({
                            'source_ids': batch_ids, 'evidence_set_sha256': batch_hash,
                            'input_char_count': payload_size, 'verdict': 'uncertain',
                            'output': None, 'reason_code': 'set_review_character_budget_exceeded'})
                        break
                    remaining_time = MAX_SET_REVIEW_SECONDS - (time.monotonic() - started)
                    if remaining_time <= 0:
                        conflict_state = 'uncertain'
                        set_review_batches.append({
                            'source_ids': batch_ids, 'evidence_set_sha256': batch_hash,
                            'input_char_count': payload_size, 'verdict': 'uncertain',
                            'output': None, 'reason_code': 'set_review_time_budget_exceeded'})
                        break
                    try:
                        verdict, groups = self._review_set(
                            question, batch, proposed_ids, remaining_time)
                    except EvidenceUnavailable as exc:
                        verdict, groups = 'unavailable', []
                        reason_code = str(exc)
                    else:
                        reason_code = None
                    covered.update(identifier for identifier in batch_ids
                                   if identifier not in selected_ids)
                    set_review_batches.append({
                        'source_ids': batch_ids,
                        'proposed_source_ids': proposed_ids,
                        'remaining_source_ids': remaining_ids,
                        'evidence_set_sha256': batch_hash,
                        'comparison_plan_sha256': plan_hash,
                        'input_char_count': payload_size,
                        'verdict': verdict,
                        'output': {'conflicts': groups} if groups else None,
                        'reason_code': reason_code,
                    })
                    conflicts.extend(groups)
                    if verdict != 'consistent':
                        conflict_state = verdict
                        break
                    if time.monotonic() - started > MAX_SET_REVIEW_SECONDS:
                        conflict_state = 'uncertain'
                        set_review_batches[-1]['reason_code'] = 'set_review_time_budget_exceeded'
                        break
                if conflict_state == 'consistent' and covered != {
                        item['chunk_id'] for item in remaining}:
                    conflict_state = 'uncertain'
            if conflict_state != 'consistent':
                answer_sources = []

        serializable = {
            'question_sha256': hashlib.sha256(question.encode()).hexdigest(),
            'index_signature': index['signature'],
            'index_generation': index['generation'],
            'index_revision': index['revision'],
            'pipeline_version': self.pipeline_version,
            'reviewer_signature': self.reviewer_signature,
            'sources': selected,
            'conflict_state': conflict_state,
            'conflicts': conflicts,
            'set_review_batches': set_review_batches,
        }
        return ReviewedSnapshot(
            question_sha256=serializable['question_sha256'],
            index_signature=index['signature'],
            index_generation=index['generation'], index_revision=index['revision'],
            pipeline_version=self.pipeline_version,
            reviewer_signature=self.reviewer_signature,
            sources=tuple(answer_sources), conflicts=tuple(conflicts),
            rejection_counts=dict(sorted(rejections.items())),
            set_review_batches=tuple(set_review_batches),
            conflict_state=conflict_state,
            snapshot_sha256=_digest(serializable))
