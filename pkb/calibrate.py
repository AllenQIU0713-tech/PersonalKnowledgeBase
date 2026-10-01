"""Measure or apply calibration for the fixed local embedding configuration."""
import argparse
import hashlib
import json
from pathlib import Path

from .config import data_directory
from .embedding import Embeddings
from .store import Store


def measure(args):
    dataset_path = Path(args.dataset)
    dataset_bytes = dataset_path.read_bytes()
    dataset = json.loads(dataset_bytes)
    store = Store(data_directory(args.data_dir))
    embeddings = Embeddings(store, args.embedding_port, args.embedding_model)
    passages = {}
    for item in dataset['passages']:
        text = embeddings.passage_text(item['title'], item.get('tags', []), item['text'])
        passages[item['id']] = embeddings.encode(text)
    results = []
    for query in dataset['queries']:
        vector = embeddings.encode(query['text'], query=True)
        scores = {identifier: sum(a * b for a, b in zip(vector, other))
                  for identifier, other in passages.items()}
        results.append({'id': query['id'], 'text': query['text'],
                        'targets': query.get('targets', []), 'scores': scores})
    output = {
        'model': args.embedding_model, 'signature': embeddings.signature,
        'dataset_sha256': hashlib.sha256(dataset_bytes).hexdigest(),
        'passage_template': embeddings.status()['passage_template'],
        'query_template': embeddings.status()['query_template'],
        'pooling': embeddings.status()['pooling'], 'results': results,
    }
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(args.output)


def apply(args):
    report = Path(args.report)
    report_bytes = report.read_bytes()
    measured = json.loads(report_bytes)
    digest = hashlib.sha256(report_bytes).hexdigest()
    store = Store(data_directory(args.data_dir))
    embeddings = Embeddings(store, None, args.embedding_model)
    status = embeddings.status()
    expected = {
        'model': args.embedding_model, 'signature': embeddings.signature,
        'passage_template': status['passage_template'],
        'query_template': status['query_template'], 'pooling': status['pooling'],
    }
    if any(measured.get(key) != value for key, value in expected.items()):
        raise ValueError('校准报告与当前固定模型或模板不匹配')
    if not isinstance(measured.get('results'), list) or not measured['results']:
        raise ValueError('校准报告没有可核对的原始分数')
    print(json.dumps(embeddings.set_calibration(args.threshold, digest), ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='operation', required=True)
    measure_parser = sub.add_parser('measure')
    measure_parser.add_argument('--dataset', required=True)
    measure_parser.add_argument('--output', required=True)
    measure_parser.add_argument('--data-dir', required=True)
    measure_parser.add_argument('--embedding-port', type=int, required=True)
    measure_parser.add_argument('--embedding-model', required=True)
    measure_parser.set_defaults(action=measure)
    apply_parser = sub.add_parser('apply')
    apply_parser.add_argument('--report', required=True)
    apply_parser.add_argument('--threshold', type=float, required=True)
    apply_parser.add_argument('--data-dir', required=True)
    apply_parser.add_argument('--embedding-model', required=True)
    apply_parser.set_defaults(action=apply)
    args = parser.parse_args()
    args.action(args)


if __name__ == '__main__':
    main()
