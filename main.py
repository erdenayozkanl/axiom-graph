import argparse, json
from axiom_graph import load_demo

parser = argparse.ArgumentParser(description="AxiomGraph: auditable GraphRAG reference")
parser.add_argument("question", nargs="?")
parser.add_argument("--hops", type=int, default=2)
parser.add_argument("--serve", action="store_true")
args = parser.parse_args()
if args.serve:
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8004)
elif args.question:
    print(json.dumps(load_demo().answer(args.question, args.hops), indent=2))
else:
    parser.print_help()
