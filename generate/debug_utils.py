from generate.parsing import Struct


def pprint_structure(structure: Struct):
    print("struct", structure.name, end=" ")

    if structure.bases:
        print(":", end="")
    for base in structure.bases:
        if base is not structure.bases[0]:
            print(", ", end="")
        else:
            print(" ", end="")
        print(base.accessibility.value, end=" ")
        if base.virtual:
            print("virtual ", end="")
        print(base.name, end="")

    print(" {")
    for member in structure.members:
        if isinstance(member, Struct.Field):
            print(f"  [field]  ", end="")
        else:
            print(f"  [method] ", end="")

        print(f"{member.accessibility.value}", end=" ")
        if isinstance(member, Struct.Field):
            print(f"{member.type} {member.name};")
        else:
            if member.virtual:
                print("virtual ", end="")
            print(f"{member.return_type} {member.name}(", end="")
            for param in member.params:
                if param is not member.params[0]:
                    print(", ", end="")
                if param == "...":
                    print("...", end="")
                else:
                    print(param.type, end="")
                    if param.name:
                        print(f" {param.name}", end="")
                    if param.default:
                        print(" =", param.default, end="")
            print(")", end="")
            if member.const:
                print(" const", end="")
            print(";")
    print("}")
