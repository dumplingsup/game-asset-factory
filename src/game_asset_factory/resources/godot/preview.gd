extends SceneTree
## Generic inspection only. No game controllers, rules or dependencies.

var world: Node3D
var model: Node3D
var camera: Camera3D
var output := ""
var model_path := ""
var material_mode := "clay"
var bounds := AABB()
var captures: Array[Dictionary] = []
var mesh_instances := 0
var triangles := 0
var material_records: Array[Dictionary] = []

func _initialize() -> void:
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("--model="):
			model_path = argument.trim_prefix("--model=")
		if argument.begins_with("--output="):
			output = argument.trim_prefix("--output=")
		if argument.begins_with("--material-mode="):
			material_mode = argument.trim_prefix("--material-mode=")
	_run.call_deferred()

func fail(message: String) -> void:
	push_error(message)
	quit(2)

func _run() -> void:
	if model_path.is_empty() or output.is_empty():
		fail("Missing model/output arguments")
		return
	var document := GLTFDocument.new()
	var state := GLTFState.new()
	var error := document.append_from_file(model_path, state)
	if error != OK:
		fail("GLB runtime import failed: %d" % error)
		return
	model = document.generate_scene(state) as Node3D
	if model == null:
		fail("GLB generated no Node3D")
		return
	world = Node3D.new()
	root.add_child(world)
	world.add_child(model)
	var first := true
	for child: Node in model.find_children("*", "MeshInstance3D", true, false):
		var instance := child as MeshInstance3D
		if instance.mesh == null:
			continue
		mesh_instances += 1
		var box := instance.get_aabb()
		for corner: int in 8:
			var point := instance.global_transform * box.get_endpoint(corner)
			if first:
				bounds = AABB(point, Vector3.ZERO)
				first = false
			else:
				bounds = bounds.expand(point)
		for surface: int in instance.mesh.get_surface_count():
			var arrays := instance.mesh.surface_get_arrays(surface)
			var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
			var positions: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			triangles += int(indices.size() / 3) if not indices.is_empty() else int(positions.size() / 3)
	if first or mesh_instances == 0:
		fail("No renderable mesh")
		return
	var environment := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color("253039")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color("bec9cf")
	env.ambient_light_energy = 0.25
	env.tonemap_mode = Environment.TONE_MAPPER_ACES
	env.glow_enabled = false
	env.ssao_enabled = true
	env.ssao_radius = 0.2
	env.ssao_intensity = 1.0
	environment.environment = env
	world.add_child(environment)
	var material := StandardMaterial3D.new()
	material.albedo_color = Color("888f91")
	material.roughness = 0.82
	# Clay is explicitly an inspection override; source mode preserves real materials.
	for child: Node in model.find_children("*", "MeshInstance3D", true, false):
		var instance := child as MeshInstance3D
		if material_mode == "clay":
			instance.material_override = material
		for surface: int in instance.mesh.get_surface_count():
			var active := instance.get_active_material(surface) as StandardMaterial3D
			if active != null:
				material_records.append({"name":active.resource_name,"albedo_texture":active.albedo_texture != null,
					"normal_texture":active.normal_texture != null,"roughness_texture":active.roughness_texture != null,
					"metallic_texture":active.metallic_texture != null,"emission_texture":active.emission_texture != null})
			if instance.get_active_material(surface) == null:
				instance.set_surface_override_material(surface, material)
	var floor_node := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2.ONE * maxf(bounds.size.length() * 6.0, 10.0)
	floor_node.mesh = plane
	floor_node.position.y = bounds.position.y - 0.01
	var floor_material := StandardMaterial3D.new()
	floor_material.albedo_color = Color("3d464d")
	floor_material.roughness = 0.9
	floor_node.material_override = floor_material
	world.add_child(floor_node)
	for description: Array in [[Vector3(-35,-35,0), 0.8], [Vector3(-25,145,0), 0.45]]:
		var light := DirectionalLight3D.new()
		light.rotation_degrees = description[0]
		light.light_energy = description[1]
		light.shadow_enabled = true
		world.add_child(light)
	camera = Camera3D.new()
	camera.current = true
	camera.near = 0.01
	camera.far = 1000.0
	world.add_child(camera)
	root.size = Vector2i(960,720)
	for description: Array in [["front", 0.0], ["back", 180.0], ["left", -90.0], ["three_quarter", -35.0]]:
		set_view(float(description[1]))
		for frame: int in 8:
			await process_frame
		await RenderingServer.frame_post_draw
		var picture := root.get_texture().get_image()
		var filename := str(description[0]) + ".png"
		if picture.save_png(output.path_join(filename)) != OK:
			fail("Cannot save preview PNG")
			return
		captures.append({"file":filename, "width":picture.get_width(), "height":picture.get_height(),
			"camera_position":array3(camera.position), "look_at":array3(bounds.get_center()), "orthographic_size":camera.size})
	for frame: int in 90:
		set_view(float(frame) * 4.0)
		await process_frame
	var report := {"schema_version":1, "runtime_glb_import":"passed", "mesh_instances":mesh_instances,
		"triangles":triangles, "bounds":{"position":array3(bounds.position),"size":array3(bounds.size)},
		"captures":captures, "materials":material_records, "material_mode":material_mode, "preview_kind":"generic inspection, no game-specific scale acceptance", "visual_review":"pending_human"}
	var file := FileAccess.open(output.path_join("preview.json"), FileAccess.WRITE)
	if file == null:
		fail("Cannot save preview report")
		return
	file.store_string(JSON.stringify(report, "\t"))
	file.close()
	print("[GAF_PREVIEW] ", JSON.stringify(report))
	quit(0)

func set_view(degrees: float) -> void:
	var center := bounds.get_center()
	var extent := maxf(maxf(bounds.size.x, bounds.size.y), bounds.size.z)
	var angle := deg_to_rad(degrees)
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = extent * 1.35
	# glTF and the sample's front face point toward -Z in this viewer.
	camera.position = center + Vector3(sin(angle), 0.05, -cos(angle)) * extent * 3.0
	camera.look_at(center)

func array3(vector: Vector3) -> Array:
	return [vector.x, vector.y, vector.z]
