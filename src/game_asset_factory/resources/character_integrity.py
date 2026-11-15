"""Geometry correspondence for actual morph round-trips, including UV seam splits."""
import math


def compare_morph_geometry(reference, actual, tolerance=0.0001):
    """Compare rest-world points and target deltas bidirectionally, not vertex indices."""
    if set(reference) != set(actual):
        raise RuntimeError('Morph mesh names changed during reimport')
    result = {}
    for name, source in reference.items():
        target = actual[name]
        if source['names'] != target['names']:
            raise RuntimeError('Morph target names/order changed: ' + name)
        max_position = max_delta = 0.0
        for first, second in ((source, target), (target, source)):
            buckets = {}
            for index, point in enumerate(second['positions']):
                key = tuple(math.floor(x / tolerance) for x in point)
                buckets.setdefault(key, []).append(index)
            for index, point in enumerate(first['positions']):
                key = tuple(math.floor(x / tolerance) for x in point)
                candidates = []
                for x in (-1, 0, 1):
                    for y in (-1, 0, 1):
                        for z in (-1, 0, 1):
                            candidates.extend(buckets.get((key[0]+x, key[1]+y, key[2]+z), ()))
                match = None
                for other in candidates:
                    distance = max(abs(a-b) for a,b in zip(point, second['positions'][other],strict=True))
                    if distance > tolerance:
                        continue
                    delta_error = max((max(abs(a-b) for a,b in zip(shape[index], other_shape[other],strict=True))
                                       for shape,other_shape in zip(first['deltas'],second['deltas'],strict=True)),default=0.0)
                    if delta_error <= tolerance:
                        match = (distance,delta_error)
                        break
                if match is None:
                    raise RuntimeError(f'Morph geometry changed: {name}, vertex {index}')
                max_position = max(max_position, match[0])
                max_delta = max(max_delta, match[1])
        result[name] = {'status':'passed','source_vertices':len(source['positions']),
                        'reimported_vertices':len(target['positions']),'targets':len(source['names']),
                        'bidirectional_correspondence':True,'tolerance_m':tolerance,
                        'max_rest_position_error_m':max_position,'max_morph_delta_error_m':max_delta}
    return result
