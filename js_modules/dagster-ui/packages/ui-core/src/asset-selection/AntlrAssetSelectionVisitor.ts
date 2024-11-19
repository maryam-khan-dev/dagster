import {AbstractParseTreeVisitor} from 'antlr4ts/tree/AbstractParseTreeVisitor';

import {
  AllExpressionContext,
  AndExpressionContext,
  AttributeExpressionContext,
  CodeLocationAttributeExprContext,
  DownTraversalExpressionContext,
  FunctionCallExpressionContext,
  FunctionNameContext,
  GroupAttributeExprContext,
  KeyExprContext,
  KeySubstringExprContext,
  KindAttributeExprContext,
  NotExpressionContext,
  OrExpressionContext,
  OwnerAttributeExprContext,
  ParenthesizedExpressionContext,
  StartContext,
  TagAttributeExprContext,
  TraversalContext,
  UpAndDownTraversalExpressionContext,
  UpTraversalExpressionContext,
  ValueContext,
} from './generated/AssetSelectionParser';
import {AssetSelectionVisitor} from './generated/AssetSelectionVisitor';
import {GraphTraverser} from '../app/GraphQueryImpl';
import {AssetGraphQueryItem} from '../asset-graph/useAssetGraphData';
import {buildRepoPathForHuman} from '../workspace/buildRepoAddress';

export class AntlrAssetSelectionVisitor
  extends AbstractParseTreeVisitor<Set<AssetGraphQueryItem>>
  implements AssetSelectionVisitor<Set<AssetGraphQueryItem>>
{
  all_assets: Set<AssetGraphQueryItem>;
  traverser: GraphTraverser<AssetGraphQueryItem>;

  protected defaultResult() {
    return new Set<AssetGraphQueryItem>();
  }

  constructor(all_assets: AssetGraphQueryItem[]) {
    super();
    this.all_assets = new Set(all_assets);
    this.traverser = new GraphTraverser(all_assets);
  }

  visitAttributeExpression(ctx: AttributeExpressionContext) {
    return this.visit(ctx.attributeExpr());
  }

  visitUpTraversalExpression(ctx: UpTraversalExpressionContext) {
    const selection = this.visit(ctx.expr());
    const traversal_depth: number = this.visit(ctx.traversal());
    for (const item of selection) {
      this.traverser.fetchUpstream(item, traversal_depth).forEach((i) => selection.add(i));
    }
    return selection;
  }

  visitUpAndDownTraversalExpression(ctx: UpAndDownTraversalExpressionContext) {
    const selection = this.visit(ctx.expr());
    const up_depth: number = this.visit(ctx.traversal(0));
    const down_depth: number = this.visit(ctx.traversal(1));
    for (const item of selection) {
      this.traverser.fetchUpstream(item, up_depth).forEach((i) => selection.add(i));
      this.traverser.fetchDownstream(item, down_depth).forEach((i) => selection.add(i));
    }
    return selection;
  }

  visitDownTraversalExpression(ctx: DownTraversalExpressionContext) {
    const selection = this.visit(ctx.expr());
    const traversal_depth: number = this.visit(ctx.traversal());
    for (const item of selection) {
      this.traverser.fetchDownstream(item, traversal_depth).forEach((i) => selection.add(i));
    }
    return selection;
  }

  visitNotExpression(ctx: NotExpressionContext) {
    const selection = this.visit(ctx.expr());
    return new Set([...this.all_assets].filter((i) => !selection.has(i)));
  }

  visitAndExpression(ctx: AndExpressionContext) {
    const left = this.visit(ctx.expr(0));
    const right = this.visit(ctx.expr(1));
    return new Set([...left].filter((i) => right.has(i)));
  }

  visitOrExpression(ctx: OrExpressionContext) {
    const left = this.visit(ctx.expr(0));
    const right = this.visit(ctx.expr(1));
    return new Set([...left, ...right]);
  }

  visitFunctionCallExpression(ctx: FunctionCallExpressionContext) {
    const function_name: string = this.visit(ctx.functionName());
    const selection = this.visit(ctx.expr());
    if (function_name === 'sinks') {
      const sinks = new Set<AssetGraphQueryItem>();
      for (const item of selection) {
        const downstream = this.traverser
          .fetchDownstream(item, Number.MAX_VALUE)
          .filter((i) => !selection.has(i));
        if (downstream.length === 0 || (downstream.length === 1 && downstream[0] === item)) {
          sinks.add(item);
        }
      }
      return sinks;
    }
    if (function_name === 'roots') {
      const roots = new Set<AssetGraphQueryItem>();
      for (const item of selection) {
        const upstream = this.traverser
          .fetchUpstream(item, Number.MAX_VALUE)
          .filter((i) => !selection.has(i));
        if (upstream.length === 0 || (upstream.length === 1 && upstream[0] === item)) {
          roots.add(item);
        }
      }
      return roots;
    }
    throw new Error(`Unknown function: ${function_name}`);
  }

  visitParenthesizedExpression(ctx: ParenthesizedExpressionContext) {
    return this.visit(ctx.expr());
  }

  visitAllExpression(_ctx: AllExpressionContext) {
    return this.all_assets;
  }

  visitKeyExpr(ctx: KeyExprContext) {
    const value: string = this.visit(ctx.value());
    return new Set([...this.all_assets].filter((i) => i.name === value));
  }

  visitKeySubstringExpr(ctx: KeySubstringExprContext) {
    const value: string = this.visit(ctx.value());
    return new Set([...this.all_assets].filter((i) => i.name.includes(value)));
  }

  visitTagAttributeExpr(ctx: TagAttributeExprContext) {
    const key: string = this.visit(ctx.value(0));
    if (ctx.EQUAL()) {
      const value: string = this.visit(ctx.value(1));
      return new Set(
        [...this.all_assets].filter((i) =>
          i.node.tags.some((t) => t.key === key && t.value === value),
        ),
      );
    }
    return new Set([...this.all_assets].filter((i) => i.node.tags.some((t) => t.key === key)));
  }

  visitOwnerAttributeExpr(ctx: OwnerAttributeExprContext) {
    const value: string = this.visit(ctx.value());
    return new Set(
      [...this.all_assets].filter((i) =>
        i.node.owners.some((o) => {
          if (o.__typename === 'TeamAssetOwner') {
            return o.team === value;
          } else {
            return o.email === value;
          }
        }),
      ),
    );
  }

  visitGroupAttributeExpr(ctx: GroupAttributeExprContext) {
    const value: string = this.visit(ctx.value());
    return new Set([...this.all_assets].filter((i) => i.node.groupName === value));
  }

  visitKindAttributeExpr(ctx: KindAttributeExprContext) {
    const value: string = this.visit(ctx.value());
    return new Set([...this.all_assets].filter((i) => i.node.kinds.some((k) => k === value)));
  }

  visitCodeLocationAttributeExpr(ctx: CodeLocationAttributeExprContext) {
    const value: string = this.visit(ctx.value());
    const selection = new Set<AssetGraphQueryItem>();
    for (const asset of this.all_assets) {
      const location = buildRepoPathForHuman(
        asset.node.repository.name,
        asset.node.repository.location.name,
      );
      if (location === value) {
        selection.add(asset);
      }
    }
    return selection;
  }

  visitStart(ctx: StartContext) {
    return this.visit(ctx.expr());
  }

  visitTraversal(ctx: TraversalContext) {
    if (ctx.STAR()) {
      return Number.MAX_SAFE_INTEGER;
    }
    if (ctx.PLUS()) {
      return ctx.PLUS().length;
    }
    throw new Error('Invalid traversal');
  }

  visitFunctionName(ctx: FunctionNameContext) {
    if (ctx.SINKS()) {
      return 'sinks';
    }
    if (ctx.ROOTS()) {
      return 'roots';
    }
    throw new Error('Invalid function name');
  }

  visitValue(ctx: ValueContext) {
    if (ctx.QUOTED_STRING()) {
      return ctx.text.slice(1, -1);
    }
    if (ctx.UNQUOTED_STRING()) {
      return ctx.text;
    }
    throw new Error('Invalid value');
  }
}