"""Measure one S2 reviewer against explicit isolated fixture data."""
import argparse
import hashlib
import json
from pathlib import Path

from .evidence_review import (
    INSTRUCT_MODEL_SHA256,
    MAX_BODY_CHARS,
    MAX_CANDIDATES,
    MAX_QUESTION_CHARS,
    MAX_TITLE_CHARS,
    PIPELINE_VERSION,
    InstructReviewer,
    ReviewError,
    ReviewInput,
    RERANKER_MODEL_SHA256,
    RerankerReviewer,
)


def _identifier(value, label):
    if not isinstance(value, str) or not value or len(value) > 200:
        raise ValueError('%s must be a nonempty string of at most 200 characters' % label)
    return value


def load_dataset(path):
    dataset_path = Path(path).resolve()
    raw = dataset_path.read_bytes()
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError('dataset exceeds 8 MiB')
    dataset = json.loads(raw)
    if not isinstance(dataset, dict) or set(dataset) != {'passages', 'queries'}:
        raise ValueError('dataset must contain only passages and queries')
    if not isinstance(dataset['passages'], list) or not dataset['passages']:
        raise ValueError('passages must be a nonempty list')
    if not isinstance(dataset['queries'], list) or not dataset['queries']:
        raise ValueError('queries must be a nonempty list')

    passages = {}
    for passage in dataset['passages']:
        expected = {'id', 'title', 'text', 'content_version', 'qualification_version'}
        if not isinstance(passage, dict) or set(passage) != expected:
            raise ValueError('each passage must contain exactly %s' % sorted(expected))
        identifier = _identifier(passage['id'], 'passage id')
        if identifier in passages:
            raise ValueError('duplicate passage id')
        item = ReviewInput('', identifier, 'x', passage['title'], passage['text'],
                           passage['content_version'], passage['qualification_version'])
        if (not isinstance(item.title, str) or len(item.title) > MAX_TITLE_CHARS
                or not isinstance(item.body, str) or not 1 <= len(item.body) <= MAX_BODY_CHARS):
            raise ValueError('passage title or text exceeds fixed limits')
        if (not isinstance(item.content_version, int) or isinstance(item.content_version, bool)
                or item.content_version < 1
                or not isinstance(item.qualification_version, int)
                or isinstance(item.qualification_version, bool)
                or item.qualification_version < 1):
            raise ValueError('passage versions must be positive integers')
        passages[identifier] = passage

    queries = []
    query_ids = set()
    for query in dataset['queries']:
        if not isinstance(query, dict) or set(query) != {'id', 'text', 'candidates'}:
            raise ValueError('each query must contain exactly id, text, and candidates')
        identifier = _identifier(query['id'], 'query id')
        if identifier in query_ids:
            raise ValueError('duplicate query id')
        query_ids.add(identifier)
        if (not isinstance(query['text'], str)
                or not 1 <= len(query['text']) <= MAX_QUESTION_CHARS):
            raise ValueError('query text exceeds fixed limits')
        candidates = query['candidates']
        if (not isinstance(candidates, list) or not 1 <= len(candidates) <= MAX_CANDIDATES
                or len(set(candidates)) != len(candidates)
                or any(candidate not in passages for candidate in candidates)):
            raise ValueError('query candidates must be 1-40 unique passage ids')
        queries.append(query)
    return raw, passages, queries


def measure(args):
    raw, passages, queries = load_dataset(args.dataset)
    if args.candidate == 'reranker':
        reviewer_context = RerankerReviewer(
            args.reranker_executable, args.model, args.timeout)
        actual_model_sha256 = RERANKER_MODEL_SHA256
    else:
        reviewer_context = InstructReviewer(args.port, args.model, args.timeout)
        actual_model_sha256 = INSTRUCT_MODEL_SHA256

    results = []
    try:
        for query in queries:
            for passage_id in query['candidates']:
                passage = passages[passage_id]
                item = ReviewInput(
                    query['id'], passage_id, query['text'], passage['title'],
                    passage['text'], passage['content_version'],
                    passage['qualification_version'])
                try:
                    result = reviewer_context.review(item)
                except ReviewError as exc:
                    result = {
                        'query_id': item.query_id, 'passage_id': item.passage_id,
                        'question_sha256': item.question_hash,
                        'evidence_sha256': item.evidence_hash,
                        'accepted': False, 'gate': 'input_rejected',
                        'error': str(exc)[:120], 'reviewer_output': None,
                    }
                results.append(result)
    finally:
        close = getattr(reviewer_context, 'close', None)
        if close:
            close()

    report = {
        'format_version': 's2-review-measurement-v1',
        'pipeline_version': PIPELINE_VERSION,
        'candidate': args.candidate,
        'model_path_name': Path(args.model).name,
        'model_sha256': actual_model_sha256,
        'dataset_sha256': hashlib.sha256(raw).hexdigest(),
        'query_count': len(queries), 'pair_count': len(results),
        'candidate_limit': MAX_CANDIDATES,
        'threshold_selected': False,
        'results': results,
    }
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    output.chmod(0o600)
    print(output)


def main():
    parser = argparse.ArgumentParser(
        description='Run one S2 reviewer only on an explicit isolated fixture dataset.')
    parser.add_argument('--candidate', choices=('reranker', 'instruct'), required=True)
    parser.add_argument('--dataset', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--timeout', type=float, default=30.0)
    parser.add_argument('--reranker-executable')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    if args.candidate == 'reranker' and not args.reranker_executable:
        parser.error('--reranker-executable is required for reranker')
    if args.candidate == 'instruct' and args.port is None:
        parser.error('--port is required for instruct')
    measure(args)


if __name__ == '__main__':
    main()
